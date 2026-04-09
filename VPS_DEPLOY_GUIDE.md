# Guia Passo-a-Passo: Subindo a Pousada System na VPS

Este guia cobre o processo exato que você deve executar no terminal da sua VPS para colocar o sistema no ar com sucesso e sem interferir nos seus outros projetos.

## Passo 1: Acessar a VPS
Abra um terminal (pode ser o prompt de comando do Windows ou PowerShell) no seu computador e conecte-se à sua VPS:
```bash
ssh root@62.171.171.184
```
*(Digite sua senha quando solicitado).*

## Passo 2: Instalar Dependências (Se necessário)
Caso a sua VPS seja uma máquina mais "crua", garanta que ela tenha o **Git** e o **Docker** instalados. Execute:
```bash
apt update
apt install git docker.io docker-compose -y
```

## Passo 3: Baixar o Projeto do GitHub
Na nuvem, navegue até a pasta onde ficam seus projetos web (geralmente `/var/www/` ou `/opt/`) e faça o "clone" do repositório finalizado:
```bash
cd /opt/
# (ou pode ser direto na pasta /root/ se preferir)

git clone https://github.com/lucasrenata/Hotelaria_ParcerIA.git
cd Hotelaria_ParcerIA
```

## Passo 4: Recriar o Arquivo `.env` (CRÍTICO)
> 🚨 **IMPORTANTE**  
> Lembra que o arquivo `.env` do backend com suas chaves da OpenAI, MercadoPago e Banco de Dados possui senhas reais? Por motivos de segurança mundial, **ele não vai pro GitHub**. Isso quer dizer que na VPS, ao baixar o repositório, o `.env` não virá.

Você precisa criar ele manualmente na VPS:
```bash
sudo nano backend/.env
```
Copie todo o texto do seu arquivo `.env` atual (o que você tem testado no seu Windows, que tem suas senhas, etc) e cole ali dentro. 

Para salvar a tela preta no *nano*: Aperte `CTRL + O`, depois dê `ENTER`, e por fim `CTRL + X` para sair.

## Passo 5: Rodar o Automotizador!
Completamente posicionado na pasta inicial, só existe uma coisa a fazer:
```bash
bash deploy.sh
```
Aqui é onde a mágica vai acontecer! O script criará o ambiente isolado "pousada_mvp", subirá os módulos de memória (Postgres), e processará as matrizes do Alembic para injetar a arquitetura de tabelas pro seu projeto funcionar sem perder nada!

## Passo 6: Roteamento Nginx (Configurando seu Domínio)
O sistema estará rodando de portas fechadas: a interface React fica na porta `5174`.
Como você usa a VPS para outras coisas e quer parear o domínio final **hotelaria.parceriacomia.com.br**, vá no **Nginx Raiz da sua VPS Host** e aponte para nosso container!

1. Crie um arquivo para esse projeto no Nginx:
```bash
nano /etc/nginx/sites-available/pousada
```

2. Cole este bloco de roteamento (*Reverse Proxy*):
```nginx
server {
    listen 80;
    server_name hotelaria.parceriacomia.com.br;

    location / {
        proxy_pass http://127.0.0.1:5174;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
*(Salve fechando: CTRL+O, ENTER, CTRL+X)*

3. Ative essa regra de domínio na VPS:
```bash
ln -s /etc/nginx/sites-available/pousada /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

> **Dica Extra!**
> Caso você gere seus SSL na máquina: Rode `certbot --nginx -d hotelaria.parceriacomia.com.br` para garantir aquele cadeado sagrado pro frontend.

## Sucesso! 
Tendo tudo validado, acesse o domínio e já estará com seu painel vivo.
