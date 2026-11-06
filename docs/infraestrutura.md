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

O script foi preparado para revisão e a criação na VPS só pode ser declarada após verificação real. Veja o registro atual em `validacao.md`.

## Execução da aplicação

O app permanece em loopback. Carregue as variáveis privadas no processo Java; o usuário do serviço não precisa ler diretamente o arquivo root se o gerenciador de serviços o carregar. Para acesso remoto ao painel, use túnel SSH privado à porta 8080. Para um Java rodando no Mac acessar PostgreSQL remoto, use túnel à porta já existente do banco e configure `DATABASE_URL` com a porta local desse túnel.

O endpoint de entrada pode receber Bearer via proxy privado específico para `/api/events`. Não encaminhar `/api/manual-events`, políticas ou demais rotas administrativas para acesso público. Não apontar o app para bancos existentes de outros projetos: Flyway cria o schema da triagem no banco configurado.

Não há deploy público ou sincronização bidirecional com GitHub nesta implementação. O Dockerfile é opcional e não foi executado no Docker local (daemon parado). O banco PostgreSQL usado na validação local é uma instância temporária separada, não o banco da VPS.
