#!/usr/bin/env python3
"""Install the private backend on the VPS host and let Spring Boot run Flyway.

Default: plan only. --apply requires root, the previously provisioned credential,
an approved JAR checksum and a free loopback port. Never prints environment values.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import tempfile
import time
from urllib.request import urlopen

RUNTIME_VERSION = "21.0.13+9.0.LTS"
RUNTIME_URL = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jre_x64_linux_hotspot_21.0.13_9.tar.gz"
RUNTIME_SHA256 = "a535a1df9c6284d9618872984e026ae0352d1f7e9e0605425c0e6114f47351dd"
SERVICE = "kipper-triagem.service"
CONTAINER = "pulsepay-db-postgres-1"
PRIVATE_ENV = Path("/etc/kipper-triagem/database.env")
INSTALL = Path("/opt/kipper-triagem")

def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def run(args, **kwargs):
    result = subprocess.run(args, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError("Etapa recusada: " + args[0] + "; inspecione no host sem publicar ambiente/credenciais")
    return result

def private_json(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or len(args.sha256) != 64 or any(c not in "0123456789abcdef" for c in args.sha256):
        raise SystemExit("Porta ou SHA-256 inválido")
    plan = {"service": SERVICE, "bind": "127.0.0.1", "port": args.port,
            "database": "triagem_java", "credential": "arquivo privado existente, sem cópia para o Mac",
            "runtime": "Eclipse Temurin " + RUNTIME_VERSION, "runtimeSha256": RUNTIME_SHA256,
            "jarSha256": args.sha256, "migration": "Flyway automático do Spring Boot, sem clean ou baseline",
            "executionUser": "systemd DynamicUser, sem privilégios administrativos",
            "aiMode": "demo", "deliveryMode": "demo"}
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2)); return
    if os.geteuid() != 0:
        raise SystemExit("Execute somente no host da VPS como root pelo canal autorizado")
    unit_path = Path("/etc/systemd/system") / SERVICE
    if unit_path.exists():
        raise SystemExit("Serviço já existe; inspecione antes de substituir ou repetir a implantação")
    meta = PRIVATE_ENV.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or stat.S_IMODE(meta.st_mode) != 0o600:
        raise SystemExit("Credencial precisa ser arquivo regular root:600")
    values = dict(line.split("=", 1) for line in PRIVATE_ENV.read_text().splitlines() if line and not line.startswith("#"))
    if values.get("DATABASE_URL") != "jdbc:postgresql://127.0.0.1:5432/triagem_java" or values.get("DATABASE_USER") != "triagem_java" or not values.get("DATABASE_PASSWORD"):
        raise SystemExit("Credencial não corresponde ao banco dedicado esperado")
    del values
    if checksum(args.jar) != args.sha256:
        raise SystemExit("Executável diverge do checksum aprovado")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    health = run(["docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER], text=True).stdout.strip()
    if health != "healthy":
        raise SystemExit("PostgreSQL não está saudável")

    # A fresh backup precedes all schema changes; the existing initial dump remains intact.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path("/var/backups/kipper-triagem")
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = backup_dir / ("triagem_java-pre-flyway-" + stamp + ".dump")
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        result = subprocess.run(["docker", "exec", CONTAINER, "pg_dump", "-U", "postgres", "-Fc", "triagem_java"], stdout=output, stderr=subprocess.PIPE)
    if result.returncode or backup.stat().st_size == 0:
        raise RuntimeError("Backup pré-migração não confirmado")
    with backup.open("rb") as archive:
        run(["docker", "exec", "-i", CONTAINER, "pg_restore", "--list"], stdin=archive)

    INSTALL.mkdir(mode=0o755, parents=True, exist_ok=True)
    releases = INSTALL / "releases"
    releases.mkdir(mode=0o755, exist_ok=True)
    artifact = releases / (args.sha256 + ".jar")
    if artifact.exists():
        if checksum(artifact) != args.sha256:
            raise RuntimeError("Release existente com conteúdo inesperado")
    else:
        shutil.copyfile(args.jar, artifact)
        artifact.chmod(0o644)
        if checksum(artifact) != args.sha256:
            raise RuntimeError("Falha na verificação da cópia do executável")
    runtime = INSTALL / "temurin-21.0.13-9"
    java = runtime / "bin/java"
    if not java.is_file():
        with tempfile.TemporaryDirectory(prefix="runtime-", dir=INSTALL) as temporary:
            archive = Path(temporary) / "jre.tar.gz"
            run(["curl", "-fsSL", "--retry", "2", RUNTIME_URL, "-o", str(archive)])
            if checksum(archive) != RUNTIME_SHA256:
                raise RuntimeError("Runtime oficial diverge do checksum da Adoptium")
            runtime.mkdir(mode=0o755, exist_ok=False)
            run(["tar", "-xzf", str(archive), "-C", str(runtime), "--strip-components=1", "--no-same-owner"])
    run([str(java), "-version"])
    runtime_env = PRIVATE_ENV.parent / "runtime.env"
    if runtime_env.exists():
        raise SystemExit("Configuração runtime já existe; revise antes de sobrescrever")
    fd = os.open(runtime_env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(f"SERVER_ADDRESS=127.0.0.1\nPORT={args.port}\nAI_MODE=demo\nDELIVERY_MODE=demo\nSPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE=5\nSPRING_DATASOURCE_HIKARI_MINIMUM_IDLE=1\n")
    unit = f"""[Unit]
Description=Kipper support triage backend
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service
StartLimitIntervalSec=120
StartLimitBurst=3

[Service]
Type=simple
DynamicUser=yes
StateDirectory=kipper-triagem-app
WorkingDirectory=/var/lib/kipper-triagem-app
EnvironmentFile={PRIVATE_ENV}
EnvironmentFile={runtime_env}
ExecStart={java} -Xms64m -Xmx256m -jar {artifact}
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
MemoryMax=512M
CPUQuota=100%
UMask=0077

[Install]
WantedBy=multi-user.target
"""
    unit_path.write_text(unit)
    unit_path.chmod(0o644)
    run(["systemd-analyze", "verify", str(unit_path)])
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", SERVICE])
    for _ in range(25):
        try:
            with urlopen(f"http://127.0.0.1:{args.port}/api/policies", timeout=2) as response:
                policies = json.load(response)
            if len(policies) == 3 and all(p["active"] for p in policies):
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("Backend não confirmou o catálogo; consulte o serviço e o Flyway no host")
    sql = "SELECT json_build_object('versions',(SELECT json_agg(version ORDER BY installed_rank) FROM flyway_schema_history WHERE success),'tables',(SELECT count(*) FROM information_schema.tables WHERE table_schema='public'),'policies',(SELECT count(*) FROM policies WHERE active),'dedicatedRoleConnections',(SELECT count(*) FROM pg_stat_activity WHERE datname='triagem_java' AND usename='triagem_java'));"
    verified = json.loads(run(["docker", "exec", CONTAINER, "psql", "-X", "-U", "postgres", "-d", "triagem_java", "-Atc", sql], text=True).stdout)
    if verified["versions"] != ["1", "2", "3"] or verified["tables"] != 8 or verified["policies"] != 3 or verified["dedicatedRoleConnections"] < 1:
        raise RuntimeError("Migrações ou conexão da aplicação ainda não confirmadas")
    run(["systemctl", "is-active", "--quiet", SERVICE])
    plan.update({"applied": True, "verifiedAt": datetime.now(timezone.utc).isoformat(), "backup": str(backup), **verified})
    receipt = Path("/var/lib/kipper-triagem") / ("backend-deployment-" + stamp + ".json")
    private_json(receipt, plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
