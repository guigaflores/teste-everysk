**Part 1: Containerization**

**Alterações no Dockerfile**

→ Utilizei a versão slim do python:3.11 para diminuir o tamanho da imagem e aprimorar a inicialização no Cloud Run

→ Separei o comando COPY requirements.txt e app.py para otimizar o cache visto que o requirements.txt não costuma haver alterações.

→ Adicionei a opção —-no-cache-dir no comando pip para evitar arquivos temporários e também diminuir o tamanho da imagem

→ Alterei “EXPOSE” para “ENV PORT” para conciliar com a variável que o Cloud Run considera do deploy

→ Vi que no arquivo requirements.txt possuía a instalação do Gunicorn, então utilizei ele, visto que a proposta do teste seria para simular um ambiente de produção, ao invés do Flask (que acredito ser mais recomendado para ambientes de desenvolvimento)

→ Adicionei o binding em 0.0.0.0:8080 para que o Cloud Run conseguisse expor a aplicação

**Part 2: GCP Deployment**

**Permissões (Contas de Serviço)**

Criei uma Conta de Serviço (task-manager-sa) e configurei as permissões para que o Cloud Run conseguisse acessar os dados no Firestore (Usuário do Cloud Datastore) e também ter acesso aos secrets (Assessor de Secret do Secret Manager)

O objetivo foi aplicar o princípio do menor privilégio (com essas 2 permissões já consegui fazer o deploy)

**Deploy Manual**

Primeiramente, pra fazer o build da imagem e o teste da aplicação, utilizei o Cloud Shell, para não precisar configurar o access token no meu terminal local. Fiz o upload manual dos arquivos, apenas para buildar a imagem e testar o deploy no Cloud Run, para ver se estava funcionando (deu certo). Adicionei a tag “prod” na imagem.

Comando para configurar o Docker para o Artifact Registry:

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev

```

Imagem:

```bash
us-central1-docker.pkg.dev/dev-everysk-playground/assessment-repo/task-manager-api:prod
```

Utilizei como database a Firestore (default), para evitar ter que fazer alterações no código da aplicação.

Ao testar os endpoints:

/health funcinou:

<img width="711" height="135" alt="imagem1" src="https://github.com/user-attachments/assets/779b8286-eea5-4fa4-acb6-e422c47445fb" />

porém /health/ready retornou o seguinte status:

{"checks":{"config":false,"firestore":true},"status":"not_ready","timestamp":"2026-01-06T14:12:39.823325"}

A database estava conectada porém não estava funcionando pois não tinha configurado as variáveis de ambiente (PROJECT e ENVIRONMENT). Depois de adicionar deu certo.

**Part 3: Automating Cloud Run Deployment with GitHub Actions**

O primeiro passo foi criar um repositório no GitHub para fazer o push do código.

Posteriormente criei uma Conta de Serviço com as permissões necessárias para que o GitHub Actions pudesse utilizar os serviços da GCP para fazer o deploy. Configurei o acesso no pipeline através da utilização da Key (JSON) da Conta de Serviço criada.

<img width="537" height="592" alt="imagem2" src="https://github.com/user-attachments/assets/61166aaf-3294-402e-86b7-b79909d22aac" />

Coloquei o "push” para o branch “main” como gatilho para acionar o pipeline, pois assim que eu fizesse o commit e o push do código ele já rodaria automaticamente.

Parâmetros sensíveis adicionei como secrets no Actions:  
GCP_SA_KEY = key no formato JSON da Conta de Serviço  
GCP_PROJECT_ID = pasta do projeto  
GCP_REGION = us-central1  

Os demais parâmetros defini como variáveis de ambiente mesmo.

Como ambiente para rodar o pipeline utilizei o ubuntu-latest.

<img width="1897" height="737" alt="imagem3" src="https://github.com/user-attachments/assets/ff7d1c12-3bf7-4d18-b45f-9ad3b5ce42d0" />
