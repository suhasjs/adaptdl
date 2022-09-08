#!/bin/bash
# clear adaptdl checkpoints
rm -rf /hot/suhasj-pollux-pvc-1d0de4e8-040c-4515-a06e-7d5629e06c21/pollux/checkpoint/*/*
# clear adaptdl job-initiated checkpoints
rm -rf /hot/suhasj-pollux-pvc-1d0de4e8-040c-4515-a06e-7d5629e06c21/pollux/checkpoint-job/*/*
# clear tensorboard
rm -rf /hot/suhasj-pollux-pvc-1d0de4e8-040c-4515-a06e-7d5629e06c21/pollux/tensorboard/*/*
