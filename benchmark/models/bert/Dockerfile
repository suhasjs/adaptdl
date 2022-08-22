#FROM nvcr.io/nvidia/pytorch:20.10-py3
FROM docker.pdl.cmu.edu/pytorch-ib:1.9.0-cuda11.1-cudnn8-devel
#FROM docker.pdl.cmu.edu/cuda-ib:11.0-devel-ubuntu18.04
WORKDIR /root

COPY adaptdl/requirements.txt requirements.txt
RUN rm /etc/apt/sources.list.d/cuda.list
RUN rm /etc/apt/sources.list.d/nvidia-ml.list
RUN apt-get update && apt-get install python3-pip -y
RUN pip3 install setuptools-rust
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt
COPY benchmark/models/bert/requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY adaptdl adaptdl
ENV PYTHONPATH=/root/adaptdl:$PYTHONPATH

COPY benchmark/models/bert bert
ENV PYTHONPATH=/root/bert:$PYTHONPATH
WORKDIR /root/bert

ENV PYTHONUNBUFFERED=true
