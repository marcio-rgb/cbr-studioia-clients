# Omni Remote Client (Linux)

Este pacote contém o cliente de navegação remota com suporte aos motores antidetect **Camoufox (Firefox C++ Stealth)** e **Playwright (Chromium Stealth)**.

## 🚀 Como Executar

1. Extraia o arquivo `omni-playwright-client-linux.zip`.
2. Escolha o motor de navegação desejado e execute no terminal:
   - 🦊 **`./start_camoufox.sh`**: Motor Antidetect Camoufox (Firefox C++ Stealth - Recomendado)
   - 🌐 **`./start_playwright.sh`**: Motor Playwright Chromium Stealth
   - ⚡ **`./start.sh`**: Inicializador padrão (Camoufox)

---

### ⚙️ Conectar a outra URL de VPS
Para conectar a um servidor diferente do padrão (`ws://ia.creditobr.com.br:8384`):

```bash
./start_camoufox.sh ws://SEU_IP_OU_DOMINIO:8384
```
