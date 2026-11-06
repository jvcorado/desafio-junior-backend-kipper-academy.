# Painel HTTPS para avaliação

**[https://kipper.jayv.cloud](https://kipper.jayv.cloud)** está publicado e foi verificado em 06/11/2026 às 20h39 (America/Sao_Paulo), com certificado/hostname válidos, redirecionamento para HTTPS e login obrigatório. [Relatório saneado](https-verificacao.json).

## Acesso

Abra o endereço e informe o usuário e a senha fornecidos no arquivo privado de acesso. O navegador apresenta seu próprio diálogo de usuário e senha (HTTP Basic sobre HTTPS). Não é necessário túnel SSH.

Esse é um acesso ao painel master: permite consultar e criar chamados, alterar políticas, revisar conflitos e realizar ações humanas de encerramento. Use somente os dados fictícios do desafio. A senha não fica no repositório, no README ou no histórico de comandos.

A cópia privada para JV foi entregue em `.private/painel-acesso.txt`, ignorada pelo Git, com permissão 600. No servidor, a configuração fica em `/etc/kipper-triagem/panel-access.json`, root:600. Compartilhe a senha diretamente com a mentora, separada do repositório público. Para usar outra conta no mesmo navegador, feche a janela privada usada na avaliação e abra outra; não há botão de logout em HTTP Basic.

## Publicação e limites

O registro DNS é somente `A kipper → 187.41.101.68`, TTL 300, no domínio existente `jayv.cloud`. Nenhum domínio novo é comprado e os demais registros são preservados.

O Traefik existente termina HTTPS com o emissor `letsencrypt`, valida a senha por hash bcrypt e limita requisições antes de encaminhar ao container exclusivo `kipper-panel-proxy`. Esse Nginx roda como UID 101, sem capabilities, com sistema de arquivos somente leitura e temporários em memória. Escuta apenas em `127.0.0.1:18083` e encaminha ao backend existente `127.0.0.1:18080`; o PostgreSQL continua privado.

O proxy rejeita outros Hosts e Origins antes de normalizar os cabeçalhos para o backend local. O acesso público a `/api/events` é bloqueado; o WhatsApp continua usando sua ponte privada e Bearer específico. O cadastro pelo painel usa `/api/manual-events`, após autenticação. Os cabeçalhos de autorização do login não chegam ao Java.

Plano e configuração revisáveis: `ops/publish_panel.py` e `ops/public-nginx.conf`. O modo padrão imprime o plano. `--preflight` valida a sintaxe e cinco limites HTTP em um container temporário privado, sem registrar rota pública. `--apply` instala somente o proxy Kipper e cria a credencial exclusiva. Por padrão gera uma senha aleatória; `--username` e `--password-file` permitem a escolha do operador, mantendo a senha em arquivo privado e removendo a entrada temporária após instalar. O instalador recusa repetir quando já existe proxy ou marcador de credencial. As imagens oficiais são resolvidas por digest na instalação e o recibo preserva o digest efetivamente usado.

`ops/verify_public_panel.py` verifica certificado/hostname, redirecionamento HTTP, bloqueio anônimo, senha incorreta, painel/API autenticados e origem das alterações, sem imprimir credenciais ou os dados dos chamados. O evento inválido de teste não cria registro.

Para suspender a publicação, remova somente o container `kipper-panel-proxy`. Isso mantém o backend privado e a integração WhatsApp em execução. Não apague os arquivos privados nem repita o instalador para trocar senha; prepare uma atualização restrita da credencial e verifique o bloqueio da senha anterior.

Referências oficiais: [HTTP Basic no Traefik](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/basicauth/) e [cabeçalhos do proxy Nginx](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header).


## Resultado verificado

- DNS A autoritativo, resolvedor público e DNS local apontando para a VPS existente.
- Certificado TLS e hostname verificados sem ignorar certificados; HTTP redireciona para HTTPS.
- Página, JavaScript e APIs retornam 401 sem login; senha incorreta também é rejeitada.
- Com o login configurado, página, arquivos estáticos, configuração e chamados retornam 200; IA real e Kanban permanecem ativos.
- Origem estrangeira e `/api/events` públicos retornam 403. Evento master inválido de mesma origem chega à validação Java e retorna 400, sem persistência.
- Serviços Kipper e ponte ativos; Hermes em execução; PostgreSQL de PulsePay e Rachô saudáveis. Nenhum serviço compartilhado precisou ser reiniciado.

A avaliação tem um único login master compartilhado. Não há perfis por pessoa, recuperação por e-mail ou logout no aplicativo; esses recursos não foram acrescentados ao backend. A verificação registra o estado da publicação; os testes de concorrência e retransmissão permanecem na suíte Java.
