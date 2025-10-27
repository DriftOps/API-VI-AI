#!/bin/bash
# ---------------------------
# Fine-tuning Gemini 2.5 Flash
# ---------------------------

TRAIN_JSON="fine_tuning/data/train.jsonl"
EVAL_JSON="fine_tuning/data/eval.jsonl"
JOB_NAME="nutricao-rag-ft"
OUTPUT_DIR="fine_tuning/output"

gcloud ai models finetune \
  --model="models/gemini-2.5-flash" \
  --dataset="$TRAIN_JSON" \
  --validation-dataset="$EVAL_JSON" \
  --train-steps=400 \
  --output-dir="$OUTPUT_DIR" \
  --region=us-central1 \
  --display-name="$JOB_NAME"

echo "Fine-tuning enviado. Verifique status com:"
echo "gcloud ai models finetune list"