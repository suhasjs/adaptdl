#FROM nvcr.io/nvidia/pytorch:20.10-py3
FROM docker.pdl.cmu.edu/pytorch-ib:1.9.0-cuda11.1-cudnn8-devel
WORKDIR /root

COPY adaptdl/requirements.txt requirements.txt
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6 -y
RUN pip3 install --no-cache-dir -r requirements.txt
COPY benchmark/models/yolov3/requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY adaptdl adaptdl
ENV PYTHONPATH=/root/adaptdl:$PYTHONPATH

COPY benchmark/models/yolov3 yolov3
ENV PYTHONPATH=/root/yolov3:$PYTHONPATH
WORKDIR /root/yolov3

RUN cd /root/yolov3/deps/apex && pip3 install -v --disable-pip-version-check --no-cache-dir ./ 
#--global-option="--cpp_ext" --global-option="--cuda_ext" ./

ENV PYTHONUNBUFFERED=true
