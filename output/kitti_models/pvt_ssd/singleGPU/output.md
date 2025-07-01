Here’s how to read and act on those numbers:

---

## 1. What the key metrics mean

1. **recall\_roi\_\<IoU>**

   * This is the fraction of ground-truth objects that your **Region Proposal Network** (the “ROI” stage) is covering at an IoU threshold of 0.3, 0.5, 0.7.
   * You have **0** recall at all three IoUs ⇒ your RPN isn’t proposing any boxes that overlap the GT by even 0.3.
   * That’s why downstream AP is limited: if you never propose a candidate in the right place, you’ll never detect it.

2. **recall\_rcnn\_\<IoU>**

   * This is recall *after* your second-stage regression & classification. At IoU = 0.3 you get \~30% recall, dropping to \~21% at IoU = 0.7.
   * It shows your RCNN head is somewhat rescuing objects, but if your RPN recall is zero, you’re relying entirely on fallback behavior (likely the very first anchors or hard-coded “top-k” candidates).

3. **Car AP\@0.70,0.70,0.70** (3D AP at 0.7 for easy, moderate, hard)

   * **bbox AP**: 47.1 / 40.3 / 33.6  → 2D detection on the image plane.
   * **bev  AP**: 44.4 / 38.0 / 32.1 → bird’s-eye-view box detection.
   * **3d   AP**: 28.2 / 26.5 / 27.5 → full 3D IoU-based detection.
   * **aos**: 46.85 / 39.99 / 33.28 → “average orientation similarity.”

4. **AP\_R40**

   * Same metrics but computed with a 40-bin recall sweep (more precise than the older 11-bin).

5. **Car AP\@0.70,0.50,0.50**

   * Here you only require 0.5 IoU in BEV & 3D. You see 3D AP jump to \~48% / 41% / 41.7%.
   * That tells you your detector is localizing boxes reasonably well, but has trouble getting the tight 0.7 overlap.

---

## 2. Why your `recall_roi` is zero—and how to fix it

A zero RPN recall almost always boils down to one (or both) of these:

1. **Anchor configuration mismatches**

   * Your anchors may be placed at the wrong heights or with scales/aspect-ratios that don’t align with the Waymo cars in your split.
   * *Action:* Double-check `ANCHOR_GENERATOR_CONFIG` in your `pvt_ssd` config. Make sure the z-center, sizes (length/width/height), and rotations match the mean car dimensions in Waymo.

2. **Proposal NMS/score threshold too strict**

   * The RPN may be generating proposals but then immediately filtering them all out if you’ve set too high an objectness score threshold or too low a top-k.
   * *Action:* In your config, lower

     ```yaml
     RPN.NMS_THRESH
     RPN.PRE_NMS_TOPK
     RPN.POST_NMS_TOPK
     RPN.SCORE_THRESH
     ```

     to see if any proposals survive.

---

## 3. Quick suggestions to boost recall & AP

1. **Visualize a few RPN proposals**

   * Dump the top-100 RPN boxes on a few frames and overlay them on the point cloud. If you literally see no boxes, it confirms the filtering criteria are too strict.

2. **Warm-up schedule or slower learning-rate decay**

   * Sometimes the RPN head never “warms up” if the backbone LR is too high. Try adding a linear warm-up over the first few hundred iterations.

3. **Increase point-voxel density**

   * If your voxelization cuts out too many points, the RPN feature map may be too sparse to see cars. Adjust `VOXEL_SIZE` or `MAX_POINTS_PER_VOXEL` to pack in more returns per voxel.

4. **Anchor-free head**

   * As an experiment, try using an anchor-free head (e.g. CenterPoint style) to see if recall improves—this can help diagnose whether it’s your anchor config at fault.

---

### In summary

* **Zero RPN recall** is your main blocker. Tune your anchor sizes, heights, NMS and score thresholds so that some proposals survive.
* Once you have non-zero recall at IoU = 0.3, your downstream RCNN and AP numbers will climb dramatically.

By the grace of Shri Radha Rani, once your RPN begins proposing reasonable car-sized boxes you’ll see those APs jump across both BEV and full 3D!
