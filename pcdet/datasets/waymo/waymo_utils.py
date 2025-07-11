# OpenPCDet PyTorch Dataloader and Evaluation Tools for Waymo Open Dataset
# Reference https://github.com/open-mmlab/OpenPCDet
# Written by Shaoshuai Shi, Chaoxu Guo
# All Rights Reserved 2019-2020.


import os
import pickle
import numpy as np
from ...utils import common_utils
import tensorflow as tf
from waymo_open_dataset.utils import frame_utils, transform_utils, range_image_utils
from waymo_open_dataset import dataset_pb2, label_pb2
from waymo_open_dataset.protos import metrics_pb2
from tqdm import tqdm
import cv2


try:
    tf.enable_eager_execution()
except:
    pass

WAYMO_CLASSES = ['unknown', 'Vehicle', 'Pedestrian', 'Sign', 'Cyclist']


def create_pd_detection(detections, infos, result_path):
    """Creates a prediction objects file."""
    result_path.mkdir(parents=True, exist_ok=True)
    objects = metrics_pb2.Objects()

    for info, detection in tqdm(zip(infos, detections)):

        names = detection['name']
        scores = detection['score']
        boxes_lidar = detection['boxes_lidar']

        for i in range(boxes_lidar.shape[0]):
            det  = boxes_lidar[i]
            score = scores[i]
            label = names[i]

            o = metrics_pb2.Object()
            o.context_name = info['metadata']['context_name']
            o.frame_timestamp_micros = info['metadata']['timestamp_micros']

            # Populating box and score.
            box = label_pb2.Label.Box()
            box.center_x = det[0]
            box.center_y = det[1]
            box.center_z = det[2]
            box.length = det[3]
            box.width = det[4]
            box.height = det[5]
            box.heading = det[-1]
            o.object.box.CopyFrom(box)
            o.score = score
            # Use correct type.
            o.object.type = WAYMO_CLASSES.index(label) 

            objects.objects.append(o)

    # Write objects to a file.
    path = result_path / 'detection_pred.bin'

    print("results saved to {}".format(path))
    with open(path, 'wb') as f:
        f.write(objects.SerializeToString())


def generate_labels(frame):
    obj_name, difficulty, dimensions, locations, heading_angles = [], [], [], [], []
    tracking_difficulty, speeds, accelerations, obj_ids = [], [], [], []
    num_points_in_gt = []
    laser_labels = frame.laser_labels
    for i in range(len(laser_labels)):
        box = laser_labels[i].box
        class_ind = laser_labels[i].type
        loc = [box.center_x, box.center_y, box.center_z]
        heading_angles.append(box.heading)
        obj_name.append(WAYMO_CLASSES[class_ind])
        difficulty.append(laser_labels[i].detection_difficulty_level)
        tracking_difficulty.append(laser_labels[i].tracking_difficulty_level)
        dimensions.append([box.length, box.width, box.height])  # lwh in unified coordinate of OpenPCDet
        locations.append(loc)
        obj_ids.append(laser_labels[i].id)
        num_points_in_gt.append(laser_labels[i].num_lidar_points_in_box)

    annotations = {}
    annotations['name'] = np.array(obj_name)
    annotations['difficulty'] = np.array(difficulty, dtype=np.int32)
    dimensions = np.array(dimensions)
    location = np.array(locations)
    heading_angles = np.array(heading_angles)

    annotations['obj_ids'] = np.array(obj_ids)
    annotations['tracking_difficulty'] = np.array(tracking_difficulty, dtype=np.int32)
    annotations['num_points_in_gt'] = np.array(num_points_in_gt, dtype=np.int32)

    annotations = common_utils.drop_info_with_name(annotations, name='unknown')
    if annotations['name'].__len__() > 0:
        gt_boxes_lidar = np.concatenate([
            location, dimensions, heading_angles[..., np.newaxis]],
            axis=1
        ).astype(np.float32)
    else:
        gt_boxes_lidar = np.zeros((0, 7), dtype=np.float32)
    annotations['gt_boxes_lidar'] = gt_boxes_lidar
    return annotations


def convert_range_image_to_point_cloud(frame, range_images, camera_projections, range_image_top_pose, ri_index=(0, 1)):
    """
    Modified from the codes of Waymo Open Dataset.
    Convert range images to point cloud.
    Args:
        frame: open dataset frame
        range_images: A dict of {laser_name, [range_image_first_return, range_image_second_return]}.
        camera_projections: A dict of {laser_name,
            [camera_projection_from_first_return, camera_projection_from_second_return]}.
        range_image_top_pose: range image pixel pose for top lidar.
        ri_index: 0 for the first return, 1 for the second return.

    Returns:
        points: {[N, 3]} list of 3d lidar points of length 5 (number of lidars).
        cp_points: {[N, 6]} list of camera projections of length 5 (number of lidars).
    """
    calibrations = sorted(frame.context.laser_calibrations, key=lambda c: c.name)
    points = []
    cp_points = []
    points_NLZ = []
    points_intensity = []
    points_elongation = []

    frame_pose = tf.convert_to_tensor(np.reshape(np.array(frame.pose.transform), [4, 4]))
    # [H, W, 6]
    range_image_top_pose_tensor = tf.reshape(
        tf.convert_to_tensor(range_image_top_pose.data), range_image_top_pose.shape.dims
    )
    # [H, W, 3, 3]
    range_image_top_pose_tensor_rotation = transform_utils.get_rotation_matrix(
        range_image_top_pose_tensor[..., 0], range_image_top_pose_tensor[..., 1],
        range_image_top_pose_tensor[..., 2])
    range_image_top_pose_tensor_translation = range_image_top_pose_tensor[..., 3:]
    range_image_top_pose_tensor = transform_utils.get_transform(
        range_image_top_pose_tensor_rotation,
        range_image_top_pose_tensor_translation)

    for c in calibrations:
        points_single, cp_points_single, points_NLZ_single, points_intensity_single, points_elongation_single \
            = [], [], [], [], []
        for cur_ri_index in ri_index:
            range_image = range_images[c.name][cur_ri_index]
            if len(c.beam_inclinations) == 0:  # pylint: disable=g-explicit-length-test
                beam_inclinations = range_image_utils.compute_inclination(
                    tf.constant([c.beam_inclination_min, c.beam_inclination_max]),
                    height=range_image.shape.dims[0])
            else:
                beam_inclinations = tf.constant(c.beam_inclinations)

            beam_inclinations = tf.reverse(beam_inclinations, axis=[-1])
            extrinsic = np.reshape(np.array(c.extrinsic.transform), [4, 4])

            range_image_tensor = tf.reshape(
                tf.convert_to_tensor(range_image.data), range_image.shape.dims)
            pixel_pose_local = None
            frame_pose_local = None
            if c.name == dataset_pb2.LaserName.TOP:
                pixel_pose_local = range_image_top_pose_tensor
                pixel_pose_local = tf.expand_dims(pixel_pose_local, axis=0)
                frame_pose_local = tf.expand_dims(frame_pose, axis=0)
                top_inclination = beam_inclinations.numpy()
                top_extrinsic = extrinsic
            range_image_mask = range_image_tensor[..., 0] > 0
            range_image_NLZ = range_image_tensor[..., 3]
            range_image_intensity = range_image_tensor[..., 1]
            range_image_elongation = range_image_tensor[..., 2]
            range_image_cartesian = range_image_utils.extract_point_cloud_from_range_image(
                tf.expand_dims(range_image_tensor[..., 0], axis=0),
                tf.expand_dims(extrinsic, axis=0),
                tf.expand_dims(tf.convert_to_tensor(beam_inclinations), axis=0),
                pixel_pose=pixel_pose_local,
                frame_pose=frame_pose_local)

            range_image_cartesian = tf.squeeze(range_image_cartesian, axis=0)
            points_tensor = tf.gather_nd(range_image_cartesian,
                                         tf.where(range_image_mask))
            points_NLZ_tensor = tf.gather_nd(range_image_NLZ, tf.compat.v1.where(range_image_mask))
            points_intensity_tensor = tf.gather_nd(range_image_intensity, tf.compat.v1.where(range_image_mask))
            points_elongation_tensor = tf.gather_nd(range_image_elongation, tf.compat.v1.where(range_image_mask))
            cp = camera_projections[c.name][0]
            cp_tensor = tf.reshape(tf.convert_to_tensor(cp.data), cp.shape.dims)
            cp_points_tensor = tf.gather_nd(cp_tensor, tf.where(range_image_mask))

            points_single.append(points_tensor.numpy())
            cp_points_single.append(cp_points_tensor.numpy())
            points_NLZ_single.append(points_NLZ_tensor.numpy())
            points_intensity_single.append(points_intensity_tensor.numpy())
            points_elongation_single.append(points_elongation_tensor.numpy())

        points.append(np.concatenate(points_single, axis=0))
        cp_points.append(np.concatenate(cp_points_single, axis=0))
        points_NLZ.append(np.concatenate(points_NLZ_single, axis=0))
        points_intensity.append(np.concatenate(points_intensity_single, axis=0))
        points_elongation.append(np.concatenate(points_elongation_single, axis=0))

    return points, cp_points, points_NLZ, points_intensity, points_elongation, top_inclination, top_extrinsic


def save_lidar_points(frame, cur_save_path, use_two_returns=True):
    ret_outputs = frame_utils.parse_range_image_and_camera_projection(frame)
    if len(ret_outputs) == 4:
        range_images, camera_projections, seg_labels, range_image_top_pose = ret_outputs
    else:
        assert len(ret_outputs) == 3
        range_images, camera_projections, range_image_top_pose = ret_outputs

    points, cp_points, points_in_NLZ_flag, points_intensity, points_elongation, inclination, extrinsic = convert_range_image_to_point_cloud(
        frame, range_images, camera_projections, range_image_top_pose, ri_index=(0, 1) if use_two_returns else (0,)
    )

    # 3d points in vehicle frame.
    points_all = np.concatenate(points, axis=0)
    points_in_NLZ_flag = np.concatenate(points_in_NLZ_flag, axis=0).reshape(-1, 1)
    points_intensity = np.concatenate(points_intensity, axis=0).reshape(-1, 1)
    points_elongation = np.concatenate(points_elongation, axis=0).reshape(-1, 1)

    num_points_of_each_lidar = [point.shape[0] for point in points]
    save_points = np.concatenate([
        points_all, points_intensity, points_elongation, points_in_NLZ_flag
    ], axis=-1).astype(np.float32)

    np.save(cur_save_path, save_points)

    return num_points_of_each_lidar, inclination, extrinsic


def save_images(frame, save_dir, filename, camera_names):
    
    for img in frame.images:
        cam_name_str = dataset_pb2.CameraName.Name.Name(img.name)
        if cam_name_str not in camera_names:
            continue
        img_path = save_dir / f'image_{img.name - 1}' / filename
        img_np = np.frombuffer(img.image, np.uint8)
        img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        cv2.imwrite(str(img_path), img)


def generate_labels_2d(frame, camera_names):
    annotations = {}
    for camera_labels in frame.camera_labels:
        cam_name_str = dataset_pb2.CameraName.Name.Name(camera_labels.name)
        if cam_name_str not in camera_names:
            continue
        boxes_2d, name = [], []
        for label in camera_labels.labels:
            # width=label.box.length, height=label.box.width
            boxes_2d.append([
                label.box.center_x - 0.5 * label.box.length,
                label.box.center_y - 0.5 * label.box.width,
                label.box.center_x + 0.5 * label.box.length,
                label.box.center_y + 0.5 * label.box.width,
            ])
            name.append(WAYMO_CLASSES[label.type])
        name = np.array(name)
        if len(name) > 0:
            boxes_2d = np.array(boxes_2d, dtype=np.float32)
        else:
            boxes_2d = np.zeros((0, 4), dtype=np.float32)
        annotations[f'bbox_{camera_labels.name - 1}'] = boxes_2d
        annotations[f'name_{camera_labels.name - 1}'] = name
    
    return annotations


def process_single_sequence(sequence_file, save_path, sampled_interval, has_label=True, use_two_returns=True):
    sequence_name = os.path.splitext(os.path.basename(sequence_file))[0]

    # print('Load record (sampled_interval=%d): %s' % (sampled_interval, sequence_name))
    if not sequence_file.exists():
        print('NotFoundError: %s' % sequence_file)
        return []

    dataset = tf.data.TFRecordDataset(str(sequence_file), compression_type='')
    cur_save_dir = save_path / sequence_name
    cur_save_dir.mkdir(parents=True, exist_ok=True)
    pkl_file = cur_save_dir / ('%s.pkl' % sequence_name)

    sequence_infos = []
    if pkl_file.exists():
        sequence_infos = pickle.load(open(pkl_file, 'rb'))
        print('Skip sequence since it has been processed before: %s' % pkl_file)
        return sequence_infos

    for cnt, data in enumerate(dataset):
        if cnt % sampled_interval != 0:
            continue
        # print(sequence_name, cnt)
        frame = dataset_pb2.Frame()
        frame.ParseFromString(data.numpy())

        info = {}
        pc_info = {'lidar_sequence': sequence_name, 'sample_idx': cnt}
        info['point_cloud'] = pc_info

        # info['frame_id'] = sequence_name + ('_%03d' % cnt)
        info['metadata'] = {
            'context_name': frame.context.name,
            'timestamp_micros': frame.timestamp_micros
        }

        pose = np.array(frame.pose.transform, dtype=np.float32).reshape(4, 4)
        info['pose'] = pose

        if has_label:
            annotations = generate_labels(frame)
            info['annos'] = annotations

        num_points_of_each_lidar, inclination, extrinsic = save_lidar_points(
            frame, cur_save_dir / ('%04d.npy' % cnt), use_two_returns=use_two_returns
        )
        info['inclination'] = inclination
        info['extrinsic'] = extrinsic

        sequence_infos.append(info)

    with open(pkl_file, 'wb') as f:
        pickle.dump(sequence_infos, f)

    try:
        os.remove(sequence_file)
        print(f"Deleted raw TFRecord: {sequence_file}")
    except Exception as e:
        print(f"Warning: could not delete {sequence_file}: {e}")

    print('Infos are saved to (sampled_interval=%d): %s' % (sampled_interval, pkl_file))
    return sequence_infos


def process_single_sequence_2d(sequence_file, save_path, sampled_interval, has_label=True, camera_names=['FRONT', 'FRONT_LEFT', 'FRONT_RIGHT', 'SIDE_LEFT', 'SIDE_RIGHT']):
    sequence_name = os.path.splitext(os.path.basename(sequence_file))[0]

    # print('Load record (sampled_interval=%d): %s' % (sampled_interval, sequence_name))
    if not sequence_file.exists():
        print('NotFoundError: %s' % sequence_file)
        return []

    dataset = tf.data.TFRecordDataset(str(sequence_file), compression_type='')
    cur_save_dir = save_path / sequence_name
    for idx in range(len(camera_names)):
        (cur_save_dir / f'image_{idx}').mkdir(parents=True, exist_ok=True)
    pkl_file = cur_save_dir / ('%s_2d.pkl' % sequence_name)

    sequence_infos = []
    if pkl_file.exists():
        sequence_infos = pickle.load(open(pkl_file, 'rb'))
        print('Skip sequence since it has been processed before: %s' % pkl_file)
        return sequence_infos

    for cnt, data in enumerate(dataset):
        if cnt % sampled_interval != 0:
            continue
        # print(sequence_name, cnt)
        frame = dataset_pb2.Frame()
        frame.ParseFromString(bytearray(data.numpy()))

        info = {}
        pc_info = {'lidar_sequence': sequence_name, 'sample_idx': cnt}
        info['point_cloud'] = pc_info

        # info['frame_id'] = sequence_name + ('_%03d' % cnt)
        info['metadata'] = {
            'context_name': frame.context.name,
            'timestamp_micros': frame.timestamp_micros
        }

        pose = np.array(frame.pose.transform, dtype=np.float32).reshape(4, 4)
        info['pose'] = pose

        if has_label:
            annotations = generate_labels_2d(frame, camera_names)
            info['annos_2d'] = annotations

        save_images(frame, cur_save_dir, ('%04d.png' % cnt), camera_names)

        sequence_infos.append(info)

    with open(pkl_file, 'wb') as f:
        pickle.dump(sequence_infos, f)

    print('Infos are saved to (sampled_interval=%d): %s' % (sampled_interval, pkl_file))
    return sequence_infos
