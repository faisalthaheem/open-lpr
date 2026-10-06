#!/usr/bin/env python3
"""Single-class plate detector on the annotated corpus.

Derived from YOLOX's default yolox_tiny experiment, with the changes the corpus
requires. YOLOX is Apache-2.0 (code and the same-repository release weights);
see DETECTOR.md for the licensing basis and for why the Ultralytics alternatives
are excluded.

Changes from the stock tiny config:

- input 640x640, not 416. Plate height has a 10th percentile of 36px, so at 416
  the smallest plates shrink to ~23px against a stride-8 head. At 640 they are
  ~45px. Multi-scale training is on, which matters more than any other setting
  for the small-plate case.
- multiscale_upsizing, so the model sees plates across a range of scales.
- Stronger augmentation, since the corpus is frame-derived with heavy
  near-duplicate redundancy and only ~1800 usable training images.
- fp32 rather than fp16: this ROCm build is numerically unstable in long fp16
  chains, and a detector this small gains nothing from fp16 on CPU inference.
"""

import os

from yolox.exp import Exp as MyExp


class Exp(MyExp):
    def __init__(self):
        super().__init__()

        # Backbone/head width from yolox_tiny.
        self.depth = 0.33
        self.width = 0.375

        # 640 rather than the checkpoint default of 416: the corpus's smallest
        # plates are 36px tall and would shrink below the stride-8 head at 416.
        self.input_size = (640, 640)
        self.test_size = (640, 640)
        self.multiscale_upsizing = True

        self.mosaic_scale = (0.5, 1.5)
        self.random_size = (10, 26)
        self.mixup_ratio_range = (0.8, 1.6)
        self.enable_mixup = True

        # Single class: plate.
        self.num_classes = 1
        self.class_names = ["plate"]

        # ~1800 training images at 640 with mosaic: many short epochs, because
        # a long schedule on this much near-duplicate data overfits fast.
        self.max_epoch = 100
        self.warmup_epochs = 5
        self.batch_size = 16
        self.num_workers = 8

        self.lr = 0.01
        self.min_lr_ratio = 0.05
        self.weight_decay = 5e-4

        self.exp_name = os.path.split(os.path.realpath(__file__))[1].split(".")[0]

        # Dataset root, relative to the YOLOX checkout since tools/train.py runs
        # from there. annotations/{train,val}2017.json sit under it, and the
        # image splits are its immediate subdirectories.
        #
        # Unrelated to the converter module name. This is a directory inside the
        # YOLOX checkout; the code that *writes* it is
        # lpr_app/ml/datasets/imanno_to_coco.py, and they are free to differ.
        # Overridden by tools/train.py via -f, which is how the merged set is
        # selected. The default stays the corpus-only layout so a plain run
        # reproduces the original detector rather than silently using whatever
        # dataset happens to be present.
        self.data_dir = "datasets/plate"
        self.train_ann = "train2017.json"
        self.val_ann = "val2017.json"
        self.data_num_workers = 8
