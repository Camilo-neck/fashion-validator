#!/bin/bash
# Lanza la inferencia de ChatGarment sobre el lote, por imagen o por texto.
#
#   chatgarment_correr.sh imagen /mnt/d/aipparel/lote100
#   chatgarment_correr.sh texto  /mnt/d/aipparel/lote100/chatgarment_texto.json
#
# Son los mismos argumentos de scripts/v1_5/*.sh de los autores menos tres:
# sin `deepspeed` como lanzador (la inferencia es un .generate() sobre una sola
# GPU), sin `--deepspeed zero2.json`, y con `--report_to none` en vez de wandb.
# Los pesos viven en D: y no dentro del disco virtual de WSL, que se llena
# contra el espacio libre de C:.
set -e

MODO=${1:?imagen|texto}
ENTRADA=${2:?ruta de entrada}
CG=${CG:-$HOME/chatgarment/ChatGarment}
PESOS=${PESOS:-/mnt/d/chatgarment}

case "$MODO" in
  imagen) GUION=scripts/evaluate_garment_v2_imggen_1float.py ;;
  texto)  GUION=scripts/evaluate_garment_v2_textgen_1float.py ;;
  *) echo "modo desconocido: $MODO" >&2; exit 2 ;;
esac

cd "$CG"
export HF_HOME="$PESOS/hf"
export TOKENIZERS_PARALLELISM=false

# El script busca el checkpoint en una ruta relativa fija; el enlace deja el
# archivo de 15 GB fuera del disco virtual.
DEST=checkpoints/try_7b_lr1e_4_v3_garmentcontrol_4h100_v4_final
mkdir -p "$DEST"
ln -sfn "$PESOS/pytorch_model.bin" "$DEST/pytorch_model.bin"

exec .venv/bin/python "$GUION" \
    --lora_enable True --lora_r 128 --lora_alpha 256 --mm_projector_lr 2e-5 \
    --model_name_or_path liuhaotian/llava-v1.5-7b \
    --version v1 \
    --data_path ./ \
    --data_path_eval "$ENTRADA" \
    --image_folder ./ \
    --vision_tower openai/clip-vit-large-patch14-336 \
    --mm_projector_type mlp2x_gelu \
    --mm_vision_select_layer -2 \
    --mm_use_im_start_end False \
    --mm_use_im_patch_token False \
    --image_aspect_ratio pad \
    --group_by_modality_length True \
    --bf16 True \
    --output_dir ./checkpoints/llava-v1.5-7b-task-lora \
    --num_train_epochs 1 \
    --per_device_train_batch_size 16 \
    --per_device_eval_batch_size 4 \
    --gradient_accumulation_steps 1 \
    --evaluation_strategy "no" \
    --save_strategy "steps" \
    --save_steps 50000 \
    --save_total_limit 1 \
    --learning_rate 2e-4 \
    --weight_decay 0. \
    --warmup_ratio 0.03 \
    --lr_scheduler_type "cosine" \
    --logging_steps 1 \
    --tf32 True \
    --model_max_length 3072 \
    --gradient_checkpointing True \
    --dataloader_num_workers 4 \
    --lazy_preprocess True \
    --report_to none
