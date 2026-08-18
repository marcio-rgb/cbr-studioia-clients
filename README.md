# CBR Agents - Clientes de Automação Visual (WebPilot)

Repositório público oficial dos clientes de automação desktop do **CBR Agents**.

Conecte seu navegador local (Linux e Windows) ao **Estúdio IA** para automação de formulários, cadastros, propostas e consultas web em tempo real.

---

## 🚀 Como Executar

### 🪟 No Windows:
1. Baixe o repositório ou o pacote ZIP.
2. Dê duplo clique em `windows/start.bat` (ou na raiz `start.bat`).
3. O instalador silencioso criará o ambiente virtual `.venv`, instalará os navegadores e abrirá o **CBR Agents Launcher**.
4. Faça login com sua conta da plataforma e selecione o navegador:
   - `[1] Playwright (Chromium)`
   - `[2] Camoufox (Firefox Anti-Detect / Stealth)`

---

### 🐧 No Linux (Ubuntu, Debian, Fedora, Arch):
1. Abra o terminal na pasta do projeto.
2. Dê permissão de execução e inicie:
   ```bash
   chmod +x linux/start.sh
   ./linux/start.sh
   ```
3. O script verificará as dependências nativas e abrirá o **CBR Agents Launcher** interativo.

---

## ⚙️ Motores de Navegação Suportados

- **Playwright (Chromium Stealth):** Modo padrão de alta performance e determinismo estrito.
- **Camoufox (Firefox C++ Stealth):** Modo furtivo avançado com emulação de hardware real e proteção contra Cloudflare, Datadome e Captchas.

---

## 🔄 Auto-Atualização Inteligente

O `launcher.py` sincroniza automaticamente a versão mais recente do motor `remote_client.py` a cada inicialização, garantindo que você sempre utilize a versão mais estável e com novos seletores sem necessidade de reinstalação.
