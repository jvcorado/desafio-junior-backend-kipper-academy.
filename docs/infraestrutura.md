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

Em falha parcial, o arquivo privado impede execução cega/recriação/rotação. Inspecione o estado antes de corrigir; não remova o marcador só para repetir o script. O provisionamento do banco não altera firewall, configuração global de SSH ou permissões dos bancos existentes.

Executado na VPS em 06/11/2026 após aprovação explícita de JV. Banco e role `triagem_java` criados, login confirmado e isolamento conferido por consulta independente. Credencial e dump inicial privados (root:600); bancos existentes saudáveis. O dump foi reconhecido por `pg_restore --list`; restauração e cobertura recorrente ainda não foram verificadas. `banco-vps-verificacao.json` preserva o recibo histórico da criação do banco vazio. Posteriormente, o backend foi conectado e V1–V4 aplicadas: o estado atual está em `backend-vps-verificacao.json` e `validacao.md`.

## Execução da aplicação

O app permanece em loopback. Carregue as variáveis privadas no processo Java; o usuário do serviço não precisa ler diretamente o arquivo root se o gerenciador de serviços o carregar. Para acesso remoto ao painel, use túnel SSH privado à porta configurada (18080 na VPS desta implantação). Para um Java rodando no Mac acessar PostgreSQL remoto, use túnel à porta já existente do banco e configure `DATABASE_URL` com a porta local desse túnel.

O endpoint de entrada pode receber Bearer via proxy privado específico para `/api/events`. Não encaminhar `/api/manual-events`, políticas ou demais rotas administrativas para acesso público. Não apontar o app para bancos existentes de outros projetos: Flyway cria o schema da triagem no banco configurado.

Não há deploy público ou sincronização bidirecional com GitHub nesta implementação. O Dockerfile é opcional e não foi executado no Docker local (daemon parado). O banco PostgreSQL usado na validação local é uma instância temporária separada, não o banco da VPS.

## Backend privado na VPS — conectado em 06/11/2026

`kipper-triagem.service` está habilitado no boot e ativo em **127.0.0.1:18080**, com usuário transitório do systemd (`DynamicUser=yes`), heap máximo de 256 MiB e limite de memória de 512 MiB. O processo usa a role `triagem_java`; a senha continua somente na VPS. Na primeira implantação, os modos eram `demo`; a ativação abaixo registra sua atualização.

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

## Ativação da IA real e do Kanban — 06/11/2026

`ops/activate_agent.py` atualizou o serviço existente com JAR SHA-256 `a6df99437b69b5141e80674d857c3aea3a716c00cb79911cef129ff2a679d2a6`. O backend confirmou `aiMode=http`, `deliveryMode=panel`; V4 acrescenta a confirmação única do Kanban. Antes da mudança, foi criado e reconhecido o dump privado `/var/backups/kipper-triagem/triagem_java-pre-agent-20261106T182827Z.dump`. Configuração do serviço e ambiente anterior também foram preservados em arquivos privados.

`kipper-triagem-bridge.service` oferece inferência somente em **127.0.0.1:18082** e entrada de suporte na interface privada **172.16.6.1:18081**, aceitando apenas o IP existente do container Hermes e Bearer próprio. A entrada permite eventos `whatsapp-kipper`, consulta e processamento desses chamados; recusa políticas, conflitos, entrada master, retry e chamados de outras origens. Não existe publicação do painel nessa porta. Não desative a checagem de origem se a rede Docker mudar: revise os IPs e a configuração privada.

O worker é um arquivo fixo, root-owned, executado no container como UID 10000; o corpo da requisição é JSON via stdin e não participa de shell/comando. A ponte aceita apenas `consult_policy`; somente o Java executa essa ferramenta. A autenticação do provedor não sai do Hermes. O serviço da ponte precisa do Docker para iniciar esse worker e, portanto, deve permanecer privado e com os arquivos sob controle administrativo.

Cinco chamadas reais passaram com consulta nativa de política, validação Java e persistência PostgreSQL. Veja `ia-real-verificacao.json`. O caso insuficiente permaneceu em revisão, sem confirmação de encaminhamento.

Para contingência da IA, ajuste somente `AI_MODE=demo` no arquivo privado de runtime e reinicie apenas `kipper-triagem.service`; mantenha a release atual e `DELIVERY_MODE=panel`. Isso preserva a migração aditiva e os registros do Kanban. Não execute `flyway clean`, não apague V4 e não publique arquivos de ambiente. Reverter a configuração do WhatsApp exige a cópia privada da configuração anterior e revisão da rota específica, preservando todas as outras rotas.

## Conectividade do WhatsApp — pendência identificada

O diagnóstico no container confirmou timeout TCP para `172.16.6.1:18081`, com UFW ativo. O hook capturou as mensagens fictícias, mas nenhum chamado `whatsapp-kipper` foi persistido. A inferência e o Kanban pela API do backend continuam sendo evidências separadas desse transporte.

`ops/configure_private_ingress.py` está preparado, mas **ainda não foi aplicado**. Por padrão, apenas imprime o plano. Com `--apply`, confere os IPs atuais do container e a configuração privada, exige UFW já ativo, preserva cópias privadas das regras e adiciona somente TCP de `172.16.6.2` para `172.16.6.1:18081`. Não habilita/desabilita UFW, não libera a porta para outras origens e não publica o painel. A aplicação aguarda a confirmação específica solicitada ao operador.

```sh
# Somente exibe o plano:
python3 ops/configure_private_ingress.py
# Após confirmação, no host pelo canal administrativo autorizado:
python3 ops/configure_private_ingress.py --apply
```

Após aplicar, conferir conexão a partir do container e resposta autenticada da ponte; então repetir o chamado fictício no WhatsApp e verificar a confirmação no banco e no painel. Regra de firewall adicionada sem esse teste não comprova entrega. Se os IPs mudarem, o script recusa executar: revisar origem e destino, preservando o Bearer e o isolamento do painel.
