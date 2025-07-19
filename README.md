# 文件名：deal_voice.py

## 技术依赖：
### 1、基于funASR 1.2.6版本
### 2、ubuntu 22.04 内核版本 5.15.0-143-generic
### 3、NVIDIA GeForce RTX 3060显卡

## 集成模型：
### 1、VAD模型 iic/speech_fsmn_vad_zh-cn-16k-common-pytorch
### 2、ASR模型iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch 
### 3、标点模型iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch
### 4、说话人验证模型iic/speech_campplus_sv_zh-cn_16k-common

## 实现功能
### 解析指定语音文件，分离语音文件中对话角色，完善时间戳及对话内容，构建对话双方完整对话信息

