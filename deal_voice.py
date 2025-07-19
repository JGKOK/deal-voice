import os
import time

import numpy as np
import torch

from funasr import AutoModel

os.environ['MODELSCOPE_CACHE'] = './models'


class DialogueRecognitionSystem:
    def __init__(self):
        print("初始化VAD模型...")
        self.vad_model = AutoModel(model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch")

        print("初始化ASR模型...")
        self.asr_model = AutoModel(model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch")

        print("初始化标点模型...")
        self.punc_model = AutoModel(model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch")

        print("初始化说话人验证模型...")
        self.sv_model = AutoModel(model="iic/speech_campplus_sv_zh-cn_16k-common")

        self.speaker_embeddings = {}
        self.next_speaker_id = 1

    def process_audio_file(self, audio_file_path):
        print(f"\n开始处理音频文件: {audio_file_path}")
        start_time = time.time()

        # 1. 语音识别
        print("正在进行语音识别...")
        asr_result = self.asr_model.generate(input=audio_file_path)
        print(f"ASR结果包含 {len(asr_result[0]['timestamp'])} 个时间戳")

        # 2. 处理ASR结果
        print("正在处理ASR结果...")
        segments = self._process_asr_result(audio_file_path, asr_result)
        print(f"获取到 {len(segments)} 个有效语音段")

        # 3. 分配说话人ID
        print("正在分配说话人ID...")
        dialogues = self._assign_speaker_ids(segments)

        # 4. 添加标点符号
        print("正在添加标点符号...")
        punctuated_dialogues = []
        for dialogue in dialogues:
            try:
                punc_result = self.punc_model.generate(input=dialogue['text'])
                if punc_result and len(punc_result) > 0:
                    punc_text = punc_result[0]['text']
                    punctuated_dialogues.append({
                        'speaker': dialogue['speaker'],
                        'text': punc_text,
                        'start': dialogue['start'],
                        'end': dialogue['end']
                    })
            except Exception as e:
                print(f"标点处理出错: {str(e)}")
                continue

        punctuated_dialogues.sort(key=lambda x: x['start'])

        end_time = time.time()
        print(f"\n处理完成，总耗时: {end_time - start_time:.2f}秒")
        print(f"最终生成 {len(punctuated_dialogues)} 条对话记录")

        return punctuated_dialogues

    def _process_asr_result(self, audio_file_path, asr_result):
        segments = []

        if not asr_result or not isinstance(asr_result, list):
            print("警告: 无效的ASR结果格式")
            return segments

        for result in asr_result:
            if isinstance(result, dict) and 'timestamp' in result:
                timestamps = result['timestamp']
                text = result.get('text', '')

                # 合并连续的时间段和文本
                merged_segments = self._merge_continuous_segments(timestamps, text)

                for seg in merged_segments:
                    embedding = self._extract_embedding(
                        audio_file_path,
                        seg['start_ms'],
                        seg['end_ms']
                    )

                    if embedding is not None:
                        segments.append({
                            'start': seg['start_sec'],
                            'end': seg['end_sec'],
                            'text': seg['text'],
                            'embedding': embedding
                        })

        return segments

    def _merge_continuous_segments(self, timestamps, text):
        """合并连续的时间段和对应的文本"""
        if not timestamps or not text:
            return []

        words = text.split()
        if len(words) != len(timestamps):
            print(f"警告: 文本单词数({len(words)})与时间戳数({len(timestamps)})不匹配")
            return []

        merged_segments = []
        current_seg = {
            'start_ms': timestamps[0][0],
            'end_ms': timestamps[0][1],
            'text': words[0],
            'start_sec': timestamps[0][0] / 1000,
            'end_sec': timestamps[0][1] / 1000
        }

        for i in range(1, len(timestamps)):
            current_end = current_seg['end_ms']
            next_start = timestamps[i][0]

            # 如果时间段连续或重叠，合并它们
            if next_start - current_end <= 300:  # 300ms间隔阈值
                current_seg['end_ms'] = timestamps[i][1]
                current_seg['end_sec'] = timestamps[i][1] / 1000
                current_seg['text'] += " " + words[i]
            else:
                merged_segments.append(current_seg)
                current_seg = {
                    'start_ms': timestamps[i][0],
                    'end_ms': timestamps[i][1],
                    'text': words[i],
                    'start_sec': timestamps[i][0] / 1000,
                    'end_sec': timestamps[i][1] / 1000
                }

        merged_segments.append(current_seg)
        return merged_segments

    def _extract_embedding(self, audio_file_path, start_ms, end_ms):
        try:
            sv_result = self.sv_model.generate(
                input=audio_file_path,
                begin_time=start_ms / 1000,  # 转换为秒
                end_time=end_ms / 1000
            )

            if isinstance(sv_result, list) and len(sv_result) > 0:
                embedding = None
                if 'embedding' in sv_result[0]:
                    embedding = sv_result[0]['embedding']
                elif 'spk_embedding' in sv_result[0]:
                    embedding = sv_result[0]['spk_embedding']

                if embedding is not None:
                    # 确保返回CPU上的numpy数组
                    if torch.is_tensor(embedding):
                        embedding = embedding.cpu().numpy()
                    return embedding

            print(f"警告：无法解析说话人特征结果: {sv_result}")
            return None
        except Exception as e:
            print(f"提取说话人特征出错({start_ms}-{end_ms}ms): {str(e)}")
            return None

    def _assign_speaker_ids(self, segments):
        dialogues = []

        for segment in segments:
            if segment.get('embedding') is None:
                continue

            speaker_id = self._identify_speaker(segment['embedding'])
            dialogues.append({
                'speaker': speaker_id,
                'text': segment['text'],
                'start': segment['start'],
                'end': segment['end']
            })

        return dialogues

    def _identify_speaker(self, embedding):
        if not self.speaker_embeddings:
            speaker_id = f"Speaker_{self.next_speaker_id}"
            self.speaker_embeddings[speaker_id] = embedding
            self.next_speaker_id += 1
            return speaker_id

        max_similarity = -1
        best_match = None

        for known_speaker, known_embedding in self.speaker_embeddings.items():
            similarity = self._cosine_similarity(embedding, known_embedding)
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = known_speaker

        return best_match if max_similarity > 0.7 else self._create_new_speaker(embedding)

    def _create_new_speaker(self, embedding):
        speaker_id = f"Speaker_{self.next_speaker_id}"
        self.speaker_embeddings[speaker_id] = embedding
        self.next_speaker_id += 1
        return speaker_id

    def _cosine_similarity(self, emb1, emb2):
        """计算余弦相似度，处理各种可能的输入类型"""
        # 转换为numpy数组
        if torch.is_tensor(emb1):
            emb1 = emb1.cpu().numpy()
        if torch.is_tensor(emb2):
            emb2 = emb2.cpu().numpy()

        # 确保是一维数组
        emb1 = np.asarray(emb1).flatten()
        emb2 = np.asarray(emb2).flatten()

        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        return dot_product / (norm1 * norm2) if norm1 * norm2 != 0 else 0

    def print_dialogue(self, dialogues):
        print("\n完整对话内容:")
        print("=" * 60)
        for dialogue in dialogues:
            print(f"[{dialogue['speaker']}]({dialogue['start']:.2f}-{dialogue['end']:.2f}s): {dialogue['text']}")
        print("=" * 60)


if __name__ == "__main__":
    print("正在初始化对话识别系统...")
    drs = DialogueRecognitionSystem()

    audio_file = "/home/ysz/FunASR/tests/demo/input/xw669-htfn8.wav"
    if not os.path.exists(audio_file):
        print(f"\n错误: 音频文件不存在: {audio_file}")
        exit()

    dialogues = drs.process_audio_file(audio_file)

    drs.print_dialogue(dialogues)

    output_file = "dialogue_result.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        for dialogue in dialogues:
            f.write(f"[{dialogue['speaker']}]({dialogue['start']:.2f}-{dialogue['end']:.2f}s): {dialogue['text']}\n")
    print(f"\n结果已保存到 {output_file}")
