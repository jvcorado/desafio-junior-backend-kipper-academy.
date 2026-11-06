#!/usr/bin/env python3
"""One-time provisioning on the VPS host. Never prints database credentials.

Default is a read-only plan. --apply requires root and an existing PostgreSQL container.
Refuses to reuse/alter an existing database, role or private environment file.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
from datetime import datetime, timezone

def scram(password):
    salt = secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 4096)
    stored = hashlib.sha256(hmac.digest(salted, b"Client Key", "sha256")).digest()
    server = hmac.digest(salted, b"Server Key", "sha256")
    enc = lambda b: base64.b64encode(b).decode()
    return f"SCRAM-SHA-256$4096:{enc(salt)}${enc(stored)}:{enc(server)}"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plan = {"database":"triagem_java", "role":"triagem_java", "container":args.container,
            "rolePrivileges":"LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS; sem memberships",
            "publicAccess":"revogado somente no banco novo e no seu schema",
            "credentials":"/etc/kipper-triagem/database.env, root:600, geradas na VPS e nunca impressas",
            "network":"nenhuma nova porta; conexão loopback existente",
            "backup":"dump inicial privado; rotina e restauração ainda devem ser validadas"}
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2)); return
    if os.geteuid() != 0:
        raise SystemExit("Execute no host da VPS como root pelo canal administrativo autorizado")
    private = Path("/etc/kipper-triagem")
    env_file = private / "database.env"
    if env_file.exists():
        raise SystemExit("Arquivo privado já existe; nenhuma credencial foi alterada")
    def sql(text, database="postgres"):
        result = subprocess.run(["docker","exec","-i",args.container,"psql","-X","-v","ON_ERROR_STOP=1","-U","postgres","-d",database,"-At"],
                                input=text, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError("PostgreSQL recusou a etapa; inspecione no host sem publicar credenciais")
        return result.stdout.strip()
    exists = sql("SELECT count(*) FROM pg_database WHERE datname='triagem_java'; SELECT count(*) FROM pg_roles WHERE rolname='triagem_java';")
    if exists.splitlines() != ["0", "0"]:
        raise SystemExit("Banco ou role já existe; nada foi alterado")
    public_business = sql("SELECT datname FROM pg_database d, LATERAL aclexplode(COALESCE(d.datacl,acldefault('d',d.datdba))) a WHERE NOT datistemplate AND datname <> 'postgres' AND a.grantee=0 AND a.privilege_type='CONNECT';")
    if public_business:
        raise SystemExit("Há banco de aplicação acessível a PUBLIC; plano precisa de isolamento adicional antes de criar a role")
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(private, 0o700)
    password = secrets.token_urlsafe(36)
    verifier = scram(password)
    # Store privately before mutation so a partially completed run is recoverable without rotation.
    fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("DATABASE_URL=jdbc:postgresql://127.0.0.1:5432/triagem_java\nDATABASE_USER=triagem_java\nDATABASE_PASSWORD=" + password + "\n")
    sql("CREATE ROLE triagem_java NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;"
        "CREATE DATABASE triagem_java OWNER triagem_java TEMPLATE template0 ENCODING 'UTF8' ALLOW_CONNECTIONS false;")
    sql("REVOKE ALL ON DATABASE triagem_java FROM PUBLIC; ALTER DATABASE triagem_java ALLOW_CONNECTIONS true;")
    sql("REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT USAGE,CREATE ON SCHEMA public TO triagem_java;", "triagem_java")
    allowed = sql("SELECT datname FROM pg_database WHERE NOT datistemplate AND datname NOT IN ('postgres','triagem_java') AND has_database_privilege('triagem_java',oid,'CONNECT');")
    if allowed:
        raise RuntimeError("Isolamento não confirmado; a role foi mantida sem LOGIN")
    sql("ALTER ROLE triagem_java LOGIN PASSWORD '" + verifier + "';")
    # Verify the dedicated login over TCP without a password in process arguments or printed output.
    probe = subprocess.run(["docker","exec","-i",args.container,"sh","-c",
                            "IFS= read -r PGPASSWORD; export PGPASSWORD; exec psql -X -h 127.0.0.1 -U triagem_java -d triagem_java -At -v ON_ERROR_STOP=1"],
                           input=password+"\nSELECT current_database(),current_user;\n", text=True, capture_output=True)
    if probe.returncode or "triagem_java|triagem_java" not in probe.stdout:
        raise RuntimeError("Banco criado, mas login ainda não confirmado; credencial preservada somente no host")
    backup_dir = Path("/var/backups/kipper-triagem")
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / ("triagem_java-initial-" + stamp + ".dump")
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        dumped = subprocess.run(["docker","exec",args.container,"pg_dump","-U","postgres","-Fc","triagem_java"], stdout=f, stderr=subprocess.PIPE)
    if dumped.returncode or backup.stat().st_size == 0:
        raise RuntimeError("Banco criado; dump inicial não confirmado")
    plan.update({"applied":True,"loginVerified":True,"initialBackup":str(backup),"existingBusinessDatabasesAccessible":False})
    print(json.dumps(plan, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
