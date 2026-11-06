# Banco na VPS e acesso privado

O pedido atual inclui um banco próprio na VPS. O script revisável `ops/provision_database.py` implementa o plano para um cluster PostgreSQL existente, sem criar porta pública e sem modificar bancos de outros projetos.

```sh
# Mostra somente o plano, sem conexão nem mutação:
python3 ops/provision_database.py --container NOME_DO_POSTGRES_EXISTENTE
# Somente no host da VPS, por canal administrativo autorizado:
python3 ops/provision_database.py --container NOME_DO_POSTGRES_EXISTENTE --apply
```

O plano cria `triagem_java`, role exclusiva sem privilégios administrativos/memberships, retira PUBLIC somente do novo banco/schema e gera credencial no próprio servidor. A role permanece NOLOGIN até verificar isolamento. O banco nasce com conexões desativadas até restringir sua ACL. Não reutiliza nem altera role/banco já existentes. Antes de qualquer criação, recusa execução se outro banco de aplicação estiver acessível a PUBLIC. A credencial fica em `/etc/kipper-triagem/database.env`, root:600; nunca deve ser impressa, incluída no GitHub, chat ou memória.

O script verifica login e produz dump inicial privado em `/var/backups/kipper-triagem`. **Dump inicial não comprova rotina de backup nem restauração.** Definir cobertura recorrente e testar recuperação antes de dados importantes. Compartilhar cluster significa compartilhar processo, volume e recursos; não é isolamento de infraestrutura.

Em falha parcial, o arquivo privado impede execução cega/recriação/rotação. Inspecione o estado antes de corrigir; não remova o marcador só para repetir o script. Nenhum script altera firewall, configuração global de SSH ou permissões dos bancos existentes.

Executado na VPS em 06/11/2026 após aprovação explícita de JV. Banco e role `triagem_java` criados, login confirmado e isolamento conferido por consulta independente. Credencial e dump inicial privados (root:600); bancos existentes saudáveis. O dump foi reconhecido por `pg_restore --list`; restauração e cobertura recorrente ainda não foram verificadas. `banco-vps-verificacao.json` preserva o recibo histórico da criação do banco vazio. Posteriormente, o backend foi conectado e V1–V3 aplicadas: o estado atual está em `backend-vps-verificacao.json` e `validacao.md`.

## Execução da aplicação

O app permanece em loopback. Carregue as variáveis privadas no processo Java; o usuário do serviço não precisa ler diretamente o arquivo root se o gerenciador de serviços o carregar. Para acesso remoto ao painel, use túnel SSH privado à porta 8080. Para um Java rodando no Mac acessar PostgreSQL remoto, use túnel à porta já existente do banco e configure `DATABASE_URL` com a porta local desse túnel.

O endpoint de entrada pode receber Bearer via proxy privado específico para `/api/events`. Não encaminhar `/api/manual-events`, políticas ou demais rotas administrativas para acesso público. Não apontar o app para bancos existentes de outros projetos: Flyway cria o schema da triagem no banco configurado.

Não há deploy público ou sincronização bidirecional com GitHub nesta implementação. O Dockerfile é opcional e não foi executado no Docker local (daemon parado). O banco PostgreSQL usado na validação local é uma instância temporária separada, não o banco da VPS.

## Backend privado na VPS — conectado em 06/11/2026

`kipper-triagem.service` está habilitado no boot e ativo em **127.0.0.1:18080**, com usuário transitório do systemd (`DynamicUser=yes`), heap máximo de 256 MiB e limite de memória de 512 MiB. O processo usa a role `triagem_java`; a senha continua somente na VPS. AI_MODE e DELIVERY_MODE permanecem `demo`, sem envios externos reais.

O Java não estava instalado no host. Foi instalado o runtime oficial Eclipse Temurin 21.0.13+9 em `/opt/kipper-triagem/temurin-21.0.13-9`, com checksum conferido a partir dos metadados da [Adoptium](https://adoptium.net/installation). Não foi alterado o Java global nem reiniciado serviço de outro projeto. O executável fica em uma release identificada por SHA-256 dentro de `/opt/kipper-triagem/releases`.

`ops/deploy_backend.py` é um instalador de **primeira implantação**: valida o JAR, o banco/usuário esperado e o arquivo root:600; verifica porta livre; gera dump pré-migração; instala o runtime com SHA-256; configura o serviço; inicia a aplicação e confere Flyway e catálogo. O script recusa substituir um serviço já existente e não executa `clean` nem `baseline`. Ele não é um atualizador automático. Valores da credencial não são impressos nem enviados ao Mac.

```sh
# Mostra o plano, sem implantar:
python3 ops/deploy_backend.py --jar /caminho/triagem.jar --sha256 SHA256_DO_JAR
# Primeira implantação, somente no host e com a credencial provisionada:
python3 ops/deploy_backend.py --jar /caminho/triagem.jar --sha256 SHA256_DO_JAR --apply
```

O Flyway aplicado pela aplicação criou sete tabelas de domínio e sua tabela de histórico. V1, V2 e V3 estão com success=true; as três políticas iniciais são consultáveis pela API e foram verificadas também por túnel SSH. Um dump novo foi criado antes das migrações, preservando o dump inicial. Essa verificação não equivale a teste de restauração nem cobertura recorrente de backup.

Para acessar o painel sem publicação, mantenha um túnel SSH com a identidade já autorizada:

```sh
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18080:127.0.0.1:18080 deploy@SEU_SERVIDOR
```

Então abra **http://localhost:18080**. Esse endereço acessa o backend da VPS conectado ao PostgreSQL. O quickstart local na porta 8080 continua sendo um ambiente separado, H2 por padrão; não há cópia automática de seus dados de demonstração para a VPS.

Consultas de operação sem expor credenciais: `systemctl is-active kipper-triagem.service`, `systemctl is-enabled kipper-triagem.service` e `curl -fsS http://127.0.0.1:18080/api/policies`. Para investigar falhas, consulte o journal no host com acesso administrativo e preserve os segredos. Não imprima o ambiente do processo ou arquivos de credenciais.
