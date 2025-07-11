import os
import subprocess

from setuptools import find_packages, setup
from torch.utils.cpp_extension import BuildExtension, CUDAExtension
import distutils.log, logging
distutils.log.set_verbosity(2)      # 0 = quiet, 1 = normal, 2 = verbose
logging.basicConfig(level=logging.DEBUG)

def get_git_commit_number():
    if not os.path.exists('.git'):
        return '0000000'

    cmd_out = subprocess.run(['git', 'rev-parse', 'HEAD'], stdout=subprocess.PIPE)
    git_commit_number = cmd_out.stdout.decode('utf-8')[:7]
    return git_commit_number


def make_cuda_ext(name, module, sources):
    cuda_ext = CUDAExtension(
        name='%s.%s' % (module, name),
        sources=[os.path.join(*module.split('.'), src) for src in sources]
    )
    return cuda_ext


def write_version_to_file(version, target_file):
    with open(target_file, 'w') as f:
        print('__version__ = "%s"' % version, file=f)


if __name__ == '__main__':
    version = '0.5.1+%s' % get_git_commit_number()
    write_version_to_file(version, 'pcdet/version.py')

    setup(
        name='pcdet',
        version=version,
        description='OpenPCDet is a general codebase for 3D object detection from point cloud',
        install_requires=[
            'numpy',
            'llvmlite',
            'numba',
            'tensorboardX',
            'easydict',
            'pyyaml',
            # 'scikit-image',
            'tqdm',
            'SharedArray',
            'pycocotools',
            'terminaltables',
            # 'einops',
            'timm',
            # 'spconv',  # spconv has different names depending on the cuda version
        ],

        author='Shaoshuai Shi',
        author_email='shaoshuaics@gmail.com',
        license='Apache License 2.0',
        packages=find_packages(exclude=['tools', 'data', 'output']),
        # cmdclass={
        #     'build_ext': BuildExtension,
        # },
        cmdclass={
            'build_ext': BuildExtension.with_options(
            parallel=os.cpu_count(),  # spawn one job per core
            verbose=True,             # print each compile command
            use_ninja=True,
            ),
        },
        ext_modules=[
            make_cuda_ext(
                name='iou3d_nms_cuda',
                module='pcdet.ops.iou3d_nms',
                sources=[
                    'src/iou3d_cpu.cpp',
                    'src/iou3d_nms_api.cpp',
                    'src/iou3d_nms.cpp',
                    'src/iou3d_nms_kernel.cu',
                ]
            ),
            make_cuda_ext(
                name='roiaware_pool3d_cuda',
                module='pcdet.ops.roiaware_pool3d',
                sources=[
                    'src/roiaware_pool3d.cpp',
                    'src/roiaware_pool3d_kernel.cu',
                ]
            ),
            make_cuda_ext(
                name='roipoint_pool3d_cuda',
                module='pcdet.ops.roipoint_pool3d',
                sources=[
                    'src/roipoint_pool3d.cpp',
                    'src/roipoint_pool3d_kernel.cu',
                ]
            ),
            make_cuda_ext(
                name='pointnet2_stack_cuda',
                module='pcdet.ops.pointnet2.pointnet2_stack',
                sources=[
                    'src/pointnet2_api.cpp',
                    'src/ball_query.cpp',
                    'src/ball_query_gpu.cu',
                    'src/group_points.cpp',
                    'src/group_points_gpu.cu',
                    'src/sampling.cpp',
                    'src/sampling_gpu.cu', 
                    'src/interpolate.cpp', 
                    'src/interpolate_gpu.cu',
                    'src/voxel_query.cpp', 
                    'src/voxel_query_gpu.cu',
                ],
            ),
            make_cuda_ext(
                name='pointnet2_batch_cuda',
                module='pcdet.ops.pointnet2.pointnet2_batch',
                sources=[
                    'src/pointnet2_api.cpp',
                    'src/ball_query.cpp',
                    'src/ball_query_gpu.cu',
                    'src/group_points.cpp',
                    'src/group_points_gpu.cu',
                    'src/interpolate.cpp',
                    'src/interpolate_gpu.cu',
                    'src/sampling.cpp',
                    'src/sampling_gpu.cu',

                ],
            ),
            make_cuda_ext(
                name='center_ops_cuda',
                module='pcdet.ops.center_ops',
                sources=[
                    'src/center_ops_api.cpp',
                    'src/draw_center.cpp',
                    'src/draw_center_kernel.cu'
                ],
            ),
            make_cuda_ext(
                name='rv_ops_cuda',
                module='pcdet.ops.rv_ops',
                sources=[
                    'src/rv_ops_api.cpp',
                    'src/rv_assigner.cpp',
                    'src/rv_assigner_gpu.cu',
                    'src/rv_query.cpp',
                    'src/rv_query_gpu.cu',
                    'src/rv_group.cpp',
                    'src/rv_group_gpu.cu'
                ]
            ),
        ],
    )
