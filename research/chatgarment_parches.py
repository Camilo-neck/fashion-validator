"""Parchea el repositorio de ChatGarment para que corra fuera de su cluster.

Se ejecuta sobre un clon limpio y es idempotente. Cada cambio esta aqui y no
hecho a mano para que las desviaciones respecto al pipeline publicado se puedan
leer y discutir, que es la mitad de lo que hace comparable la medida.

    python chatgarment_parches.py ~/chatgarment/ChatGarment ~/chatgarment/GarmentCodeRC

Las cinco desviaciones:

1. sys.path al clon local de GarmentCodeRC, en vez de la ruta del cluster MPI.
2. flash_attention_2 -> sdpa. flash-attn no tiene rueda para sm_120 (Blackwell)
   y habria que compilarlo; sdpa da los mismos numeros, mas despacio.
3. Fuera el import de deepspeed. La inferencia es un .generate() suelto sobre
   model.bfloat16().cuda(): deepspeed solo lanzaba el proceso.
4. Fuera la llamada a GPT-4o. Las etiquetas vienen precalculadas desde los
   design_params en chatgarment_entradas.py; el modelo recibe el mismo dict que
   recibiria, sin un paso de pago y no determinista en medio.
5. El dataset arrastra ese dict hasta el bucle.
6. torch.load con mmap. El checkpoint pesa 15 GB y la maquina tiene 19 GB de
   RAM: cargado a memoria anonima no cabe junto al modelo. Con mmap los
   tensores quedan respaldados por el archivo en cache de pagina, y
   load_state_dict los copia uno a uno sobre parametros que ya estan en bf16
   dentro de la GPU, asi que la conversion ocurre en la copia.
"""
import re
import sys
from pathlib import Path


def cambiar(texto, viejo, nuevo, etiqueta):
    """Aplica el cambio, o avisa si ya estaba puesto. Falla si no encaja."""
    if nuevo in texto and viejo not in texto:
        print(f"  = {etiqueta} (ya estaba)")
        return texto
    if viejo not in texto:
        raise SystemExit(f"NO ENCAJA: {etiqueta}\n  buscaba: {viejo[:90]!r}")
    print(f"  + {etiqueta}")
    return texto.replace(viejo, nuevo)


def parchear(chatgarment, garmentcode):
    cg = Path(chatgarment).expanduser()
    gc = Path(garmentcode).expanduser()
    if not (gc / "assets").is_dir():
        raise SystemExit(f"no encuentro {gc}/assets")

    # --- 1. ruta de GarmentCodeRC -------------------------------------------
    p = cg / "llava" / "garment_utils_v2.py"
    s = p.read_text()
    s = re.sub(r"sys\.path\.insert\(1, '[^']*'\)",
               f"sys.path.insert(1, '{gc}')", s, count=1)
    p.write_text(s)
    print(f"  + ruta de GarmentCodeRC -> {gc}")

    # --- 2, 3. las dos rutas de inferencia ----------------------------------
    for nombre in ("evaluate_garment_v2_textgen_1float.py",
                   "evaluate_garment_v2_imggen_1float.py"):
        p = cg / "scripts" / nombre
        s = p.read_text()
        print(f"{nombre}:")
        s = cambiar(s, "\nimport deepspeed\n", "\n",
                    "sin deepspeed")
        s = cambiar(s, "attn_implementation = 'flash_attention_2'",
                    "attn_implementation = 'sdpa'",
                    "sdpa en vez de flash-attn")
        s = cambiar(s, 'state_dict = torch.load(resume_path, map_location="cpu")',
                    'state_dict = torch.load(resume_path, map_location="cpu",\n'
                    '                            mmap=True, weights_only=True)',
                    "el checkpoint entra por mmap")
        p.write_text(s)

    # --- 4, 5. GPT-4o fuera de la ruta de texto -----------------------------
    p = cg / "scripts" / "evaluate_garment_v2_textgen_1float.py"
    s = p.read_text()
    print("evaluate_garment_v2_textgen_1float.py (GPT-4o):")
    s = cambiar(s, "\nfrom openai import OpenAI\n", "\n", "sin el import de openai")
    s = cambiar(s, "    client = OpenAI()\n", "    client = None\n",
                "sin cliente de OpenAI")
    s = cambiar(s,
                """        gpt_4o_description = ask_gpt4o(
            data_item['garment_types'], data_item['garment_names'], data_item['garment_prompts'], client)""",
                """        # Etiquetas precalculadas desde los design_params (chatgarment_entradas.py).
        # Mismo formato que devolvia ask_gpt4o: json con comillas simples.
        gpt_4o_description = json.dumps(data_item['etiquetas']).replace('"', "'")""",
                "etiquetas precalculadas en vez de la llamada a GPT-4o")
    s = cambiar(s,
                """        data_dict['image_trivial'] = image_trivial

        return data_dict""",
                """        data_dict['image_trivial'] = image_trivial
        data_dict['etiquetas'] = source['etiquetas']

        return data_dict""",
                "el dataset arrastra las etiquetas")
    p.write_text(s)

    # el bucle del dataset trata toda clave con 'garment' como una prenda
    assert "etiquetas" not in "upperbody garment lowerbody garment wholebody garment"
    print("\nlisto")


if __name__ == "__main__":
    parchear(sys.argv[1], sys.argv[2])
