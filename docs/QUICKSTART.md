# Quick Start

This guide is for a clean server deployment.

## 1. Install prerequisites

Install Docker, Docker Compose, and Git on your server.

For Ubuntu-based servers:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
```

Install Docker using the official Docker installation guide for your operating system.

---

## 2. Clone the project

```bash
git clone https://github.com/bahram-khakbaz/ai-license-plate-access-platform.git
cd ai-license-plate-access-platform
```

---

## 3. Create configuration

```bash
cp .env.example .env
nano .env
```

Set at least:

```text
SECRET_KEY=change-this-to-a-long-random-value
APP_PORT=5000
AUTH_MODE=local
```

---

## 4. Create runtime directories

```bash
mkdir -p data uploads exports logs backups
```

---

## 5. Start the platform

```bash
docker compose up -d --build
```

---

## 6. Check service status

```bash
docker compose ps
docker compose logs -f
```

Health check:

```bash
bash scripts/healthcheck.sh
```

---

## 7. Open the panel

```text
http://SERVER_ADDRESS:5000
```

If you changed `APP_PORT`, use that port.

---

## 8. Update the platform

```bash
git pull
docker compose up -d --build
```

---

## 9. Backup

```bash
bash scripts/backup.sh
```

Backups are stored under:

```text
backups/
```

---

## Important Note

This repository includes deployment scaffolding and documentation. Application source files must also exist in the repository for a complete runnable build.

Do not upload production secrets, real camera URLs, runtime databases, or captured vehicle images to Git.
