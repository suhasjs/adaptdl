FROM docker.pdl.cmu.edu/pytorch-ib:1.9.0-cuda11.1-cudnn8-devel
RUN rm /etc/apt/sources.list.d/cuda.list
RUN rm /etc/apt/sources.list.d/nvidia-ml.list
# FROM nvcr.io/nvidia/pytorch:20.03-py3
WORKDIR /root

COPY adaptdl/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY benchmark/models/cifar10/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY adaptdl adaptdl
ENV PYTHONPATH=/root/adaptdl:$PYTHONPATH

COPY benchmark/models/cifar10 cifar10
ENV PYTHONPATH=/root/cifar10:$PYTHONPATH
WORKDIR /root/cifar10

ENV PYTHONUNBUFFERED=true
