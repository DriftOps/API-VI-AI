@echo off
REM ---------------------------
REM Fine-tuning Gemini 2.5 Flash
REM ---------------------------

REM Define caminho dos datasets
set TRAIN_JSON=fine_tuning\data\train.jsonl
set EVAL_JSON=fine_tuning\data\eval.jsonl

REM Nome do display do job
set JOB_NAME=nutricao-rag-ft

REM Output do modelo FT
set OUTPUT_DIR=fine_tuning\output

REM Rodar fine-tuning
gcloud ai models finetune ^
    --model="models/gemini-2.5-flash" ^
    --dataset="%TRAIN_JSON%" ^
    --validation-dataset="%EVAL_JSON%" ^
    --train-steps=400 ^
    --output-dir="%OUTPUT_DIR%" ^
    --region=us-central1 ^
    --display-name="%JOB_NAME%"

echo Fine-tuning enviado. Verifique status com:
echo gcloud ai models finetune list
pause