"""Repete a validação sem hardware e registra saídas, versões e hashes.

Executar da raiz: python scripts/validar_offline.py
Usa o mesmo Python/venv para testes e vídeos; não abre câmera nem publica MQTT.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def executar(argumentos, saida):
    """Executa sem shell e guarda stdout/stderr, inclusive quando houver falha."""
    resultado = subprocess.run(
        [sys.executable, "-B", *argumentos],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=False,
    )
    saida.write_text(resultado.stdout + resultado.stderr, encoding="utf-8")
    return {"argumentos_python": argumentos, "exit_code": resultado.returncode}


def revisao_git():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=ROOT / "docs" / "evidencias",
                        help="pasta dos relatórios (arquivos homônimos são atualizados)")
    args = parser.parse_args()
    saida = args.saida.resolve()
    saida.mkdir(parents=True, exist_ok=True)

    # Hashes identificam o conteúdo testado mesmo antes de criar um commit.
    arquivos = sorted(set(
        list((ROOT / "pi").glob("*.py"))
        + list((ROOT / "pi" / "tests").rglob("*.py"))
        + [p for p in (ROOT / "pi" / "tests").rglob("*")
           if p.suffix in {".jpeg", ".mp4", ".txt"}]
        + [ROOT / "pi" / nome for nome in ("quadrado.jpeg", "triangulo.jpeg", "erro.jpeg")
           if (ROOT / "pi" / nome).exists()]
        + [ROOT / "pi" / "requirements-test.txt", Path(__file__).resolve()]
    ))
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in arquivos}
    versoes = {}
    for pacote in ("opencv-python", "numpy", "paho-mqtt", "pytest"):
        try:
            versoes[pacote] = importlib.metadata.version(pacote)
        except importlib.metadata.PackageNotFoundError:
            versoes[pacote] = None

    print("Executando testes e avaliando vídeos, sem hardware...", flush=True)
    testes = executar(["-m", "pytest", "pi/tests", "-q", "-p", "no:cacheprovider"],
                      saida / "pytest.txt")
    videos = executar(["pi/evaluate_videos.py", "pi/tests/videos", "--csv",
                       str(saida / "avaliacao-videos.csv")], saida / "videos.txt")
    registro = {
        "data_utc": datetime.now(timezone.utc).isoformat(),
        "plataforma": platform.platform(), "python": platform.python_version(),
        "revisao_base_git": revisao_git(),
        "identificacao_conteudo": "SHA-256 abaixo inclui alterações ainda não commitadas",
        "pacotes": versoes, "testes": testes, "videos": videos,
        "escopo": "Offline; não valida câmera CSI, firmware, eletrônica, MQTT ou saída física",
        "sha256": hashes,
    }
    (saida / "ambiente.json").write_text(
        json.dumps(registro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    print(f"Relatórios: {saida}")
    print(f"Códigos de saída: testes={testes['exit_code']}, vídeos={videos['exit_code']}")
    # Sucesso de execução não significa 100% de acerto: conferir o CSV/gabaritos.
    return int(testes["exit_code"] != 0 or videos["exit_code"] != 0)


if __name__ == "__main__":
    raise SystemExit(main())
