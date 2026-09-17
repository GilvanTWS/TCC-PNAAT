"""Avalia vídeos gravados da esteira contra suas sequências esperadas."""

import argparse
import csv
from pathlib import Path
import unicodedata

CLASSES_VALIDAS = {"QUADRADO", "TRIANGULO", "QUADRADO_COM_X"}


def normalizar_classe(valor):
    """Converte acentos, espaços e aliases para o rótulo do gabarito."""
    sem_acento = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", valor.strip().upper())
        if unicodedata.category(caractere) != "Mn"
    )
    return sem_acento.replace(" ", "_").replace("-", "_")


def ler_gabarito(path):
    """Lê uma classe por linha e rejeita rótulos desconhecidos."""
    sequencia = []
    for numero, linha in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        classe = normalizar_classe(linha)
        if not classe or classe.startswith("#"):
            continue
        if classe not in CLASSES_VALIDAS:
            raise ValueError(f"{path}:{numero}: classe inválida: {linha.strip()}")
        sequencia.append(classe)
    if not sequencia:
        raise ValueError(f"gabarito vazio: {path}")
    return sequencia


def classe_pelo_nome(video_path):
    """Infere a classe dos vídeos homogêneos pelo prefixo do arquivo."""
    nome = Path(video_path).stem.lower()
    if nome.startswith("quadrado_com_x"):
        return "QUADRADO_COM_X"
    if nome.startswith("quadrado"):
        return "QUADRADO"
    if nome.startswith("triangulo"):
        return "TRIANGULO"
    return None


def alinhar_sequencias(esperada, detectada):
    """Alinha com custo unitário de troca, perda e inserção (Levenshtein).

    Assim uma perda não transforma todas as peças seguintes em erros. Em
    empates, prioriza igualdade, troca, perda e extra, nessa ordem.
    """
    linhas = len(esperada) + 1
    colunas = len(detectada) + 1
    custo = [[0] * colunas for _ in range(linhas)]

    for i in range(linhas):
        custo[i][0] = i
    for j in range(colunas):
        custo[0][j] = j

    for i in range(1, linhas):
        for j in range(1, colunas):
            troca = 0 if esperada[i - 1] == detectada[j - 1] else 1
            custo[i][j] = min(
                custo[i - 1][j] + 1,
                custo[i][j - 1] + 1,
                custo[i - 1][j - 1] + troca,
            )

    alinhamento = []
    i, j = len(esperada), len(detectada)
    while i or j:
        if (
            i and j
            and esperada[i - 1] == detectada[j - 1]
            and custo[i][j] == custo[i - 1][j - 1]
        ):
            alinhamento.append(("correta", esperada[i - 1], detectada[j - 1]))
            i -= 1
            j -= 1
        elif i and j and custo[i][j] == custo[i - 1][j - 1] + 1:
            alinhamento.append(("incorreta", esperada[i - 1], detectada[j - 1]))
            i -= 1
            j -= 1
        elif i and custo[i][j] == custo[i - 1][j] + 1:
            alinhamento.append(("perdida", esperada[i - 1], None))
            i -= 1
        else:
            alinhamento.append(("extra", None, detectada[j - 1]))
            j -= 1

    alinhamento.reverse()
    return alinhamento


def resumir(video, esperada, detectada, resultado_video):
    alinhamento = alinhar_sequencias(esperada, detectada)
    contagens = {
        tipo: sum(1 for item in alinhamento if item[0] == tipo)
        for tipo in ("correta", "incorreta", "perdida", "extra")
    }
    # Penaliza também detecções extras, em vez de premiar contagens duplicadas.
    denominador = max(len(esperada), len(detectada), 1)
    return {
        "video": Path(video).name,
        "esperadas": len(esperada),
        "detectadas": len(detectada),
        "corretas": contagens["correta"],
        "incorretas": contagens["incorreta"],
        "perdidas": contagens["perdida"],
        "extras": contagens["extra"],
        "acerto_percentual": round(100 * contagens["correta"] / denominador, 1),
        "fps_video": resultado_video["fps"],
        "frames": resultado_video["frames_processados"],
        "alinhamento": alinhamento,
    }


def encontrar_videos(entrada):
    entrada = Path(entrada)
    if entrada.is_file():
        return [entrada]
    if entrada.is_dir():
        return sorted(entrada.glob("*.mp4"))
    raise FileNotFoundError(f"caminho não encontrado: {entrada}")


def avaliar(video, roi=None, total_classe=None):
    # Importa o pipeline pesado apenas quando um vídeo será processado. Assim,
    # leitura dos gabaritos e testes de alinhamento não dependem do OpenCV.
    from main import processar_video

    resultado = processar_video(video, roi=roi, exibir=False, tempo_real=False)
    if "erro" in resultado:
        raise RuntimeError(resultado["erro"])

    detectada = [normalizar_classe(e["classe"]) for e in resultado["eventos"]]
    gabarito = Path(video).with_suffix(".txt")
    if gabarito.exists():
        esperada = ler_gabarito(gabarito)
    else:
        classe = classe_pelo_nome(video)
        esperada = [classe] * total_classe if classe and total_classe else None

    if esperada is None:
        return None, detectada, resultado
    return resumir(video, esperada, detectada, resultado), detectada, resultado


def imprimir_resumo(resumo):
    print(
        f"{resumo['video']:<25} "
        f"esp={resumo['esperadas']:>3} det={resumo['detectadas']:>3} "
        f"ok={resumo['corretas']:>3} err={resumo['incorretas']:>3} "
        f"perd={resumo['perdidas']:>3} extra={resumo['extras']:>3} "
        f"acerto={resumo['acerto_percentual']:>5.1f}%"
    )
    for tipo, esperado, detectado in resumo["alinhamento"]:
        if tipo != "correta":
            print(
                f"    {tipo:<9} esperado={esperado or '-':<16} "
                f"detectado={detectado or '-'}"
            )


def salvar_csv(path, resumos):
    campos = [
        "video", "esperadas", "detectadas", "corretas", "incorretas",
        "perdidas", "extras", "acerto_percentual", "fps_video", "frames",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        for resumo in resumos:
            escritor.writerow({campo: resumo[campo] for campo in campos})


def main():
    parser = argparse.ArgumentParser(
        description="Avalia os vídeos da esteira com o classificador TRIA",
        allow_abbrev=False,
    )
    parser.add_argument("entrada", help="arquivo MP4 ou pasta com vídeos")
    parser.add_argument(
        "--roi", nargs=4, type=int, metavar=("X", "Y", "W", "H"),
        help="usa a mesma ROI informada no main.py",
    )
    parser.add_argument(
        "--total-classe", type=int, metavar="N",
        help="total esperado em cada vídeo sem TXT (quadrado/triangulo/X)",
    )
    parser.add_argument("--csv", help="salva o resumo também em CSV")
    args = parser.parse_args()

    if args.total_classe is not None and args.total_classe <= 0:
        parser.error("--total-classe deve ser maior que zero")

    try:
        videos = encontrar_videos(args.entrada)
    except FileNotFoundError as exc:
        parser.error(str(exc))
    if not videos:
        parser.error("nenhum arquivo .mp4 encontrado")

    roi = tuple(args.roi) if args.roi else None
    resumos = []
    sem_gabarito = []

    for video in videos:
        print(f"\nProcessando {video}...")
        try:
            resumo, detectada, _ = avaliar(
                video, roi=roi, total_classe=args.total_classe
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"ERRO: {exc}")
            continue

        if resumo is None:
            sem_gabarito.append(video.name)
            print(
                "Sem TXT/total esperado; sequência detectada: "
                + (", ".join(detectada) if detectada else "nenhuma")
            )
        else:
            resumos.append(resumo)
            imprimir_resumo(resumo)

    if resumos:
        totais = {
            campo: sum(item[campo] for item in resumos)
            for campo in (
                "esperadas", "detectadas", "corretas", "incorretas",
                "perdidas", "extras",
            )
        }
        denominador = max(totais["esperadas"], totais["detectadas"], 1)
        print("\nTOTAL")
        print(
            f"esperadas={totais['esperadas']} detectadas={totais['detectadas']} "
            f"corretas={totais['corretas']} incorretas={totais['incorretas']} "
            f"perdidas={totais['perdidas']} extras={totais['extras']} "
            f"acerto={100 * totais['corretas'] / denominador:.1f}%"
        )

    if sem_gabarito:
        print(
            "\nSem gabarito: " + ", ".join(sem_gabarito)
            + ". Use --total-classe N para avaliá-los."
        )

    if args.csv and resumos:
        salvar_csv(args.csv, resumos)
        print(f"Relatório CSV salvo em {args.csv}")
    return 0 if resumos else 1


if __name__ == "__main__":
    raise SystemExit(main())
