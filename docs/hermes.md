# Integração Hermes

Perfil dedicado: `kipper-triagem`. Criado em 06/11/2026 no Mac e na VPS, sem clonar config, credenciais, canais, memórias ou skills de outros perfis. A criação do perfil não comprova modelo autenticado, gateway ativo, ponte instalada nem entrada WhatsApp testada.

## Estado de ativação em 06/11/2026

O perfil agora tem gateway ativo e modelo real `gpt-6.1-sol/openai-codex`. A ponte privada e o worker de inferência foram implantados na VPS; cinco análises reais passaram pelo harness Java e aparecem no Kanban. JV escolheu esse Kanban como destino, sem criar issues GitHub para o teste.

O grupo **Kipper · Triagem de teste**, somente com JV e JAYV, foi criado após confirmação específica. O vínculo por rota e o plugin de recepção estão preparados, mas **não foram confirmados em execução**. Não considerar a criação do grupo como prova de atendimento automatizado funcionando.

O pacote nativo em `integrations/hermes/kipper_plugin` oferece somente `register_support_ticket` e `check_support_ticket`. O hook registra mensagens recebidas com IDs do transporte e horário da primeira observação da integração; o modelo não fornece esses metadados. Nome, telefone e mensagem precisam constar literalmente nas mensagens recentes do mesmo remetente/conversa. A consulta se limita a chamados registrados nesse atendimento. O processamento Java é uma segunda etapa explícita da ferramenta, separada do recebimento.

`occurredAt` nessa integração representa o horário observado pela recepção, preservado em reentregas; não afirma ser o horário original de envio do WhatsApp. O registro de origem usa SHA-256 de conversa, remetente e ID original da mensagem. A integração precisa confirmar no teste real que o hook recebe o texto e o contexto do transporte corretamente.

`ops/connect_whatsapp.py` instala um bundle com checksum, valida nome e dois participantes, preserva backup privado de configuração/SOUL, acrescenta uma rota exata sem remover as demais e restringe toolsets do perfil às ferramentas de suporte e memória existentes. A configuração preserva o contrato de segundo cérebro já presente no SOUL. Solicita reinício gracioso que drena turnos ativos para carregar a rota no transporte compartilhado. O script ainda precisa ser executado e validado no grupo; não é um atualizador para execução cega repetida.

## Entrada por ferramenta MCP

O arquivo `integrations/hermes/mcp_server.py` usa somente Python padrão. Fornece duas ferramentas: `receive_support_event` e `get_support_ticket`. URLs vêm da configuração do operador, nunca dos argumentos do modelo. Não fornece SQL, terminal, edição de políticas ou criação direta de issues.

No host que consegue alcançar o backend, cadastre no perfil um servidor MCP stdio com formato equivalente a:

```json
{
  "mcp_servers": {
    "kipper_triagem": {
      "command": "python3",
      "args": ["/caminho/do/repositorio/integrations/hermes/mcp_server.py"],
      "env": {"TRIAGEM_URL": "http://127.0.0.1:8080"}
    }
  }
}
```

Configure `WEBHOOK_TOKEN` no ambiente privado do bridge se o backend exigir Bearer. Não coloque o token em exemplos versionados. Instale o conteúdo de `SOUL.md` do projeto somente no perfil dedicado e permita apenas essas ferramentas. Habilitar terminal/administração nesse perfil desfaz o limite de capacidade pretendido. Perfis do Hermes compartilham UID e não constituem fronteira de isolamento do sistema operacional.

Se Java roda no Mac e Hermes na VPS, `127.0.0.1` aponta para máquinas diferentes. O bridge precisa de túnel privado ou backend implantado no mesmo host/rede privada; não use o localhost errado nem exponha o painel para resolver conectividade.

Antes de receber pelo WhatsApp, escolher conversa privada ou grupo **de teste**, autenticar o modelo do perfil por mecanismo suportado, vincular o canal e validar como o transporte entrega ID estável do evento, atendimento, cliente, nome, número e horário. O perfil deve pedir nome/número ausentes e não criar cadastro incompleto. O estado temporário dessa conversa pertence ao Hermes e ainda requer teste no canal escolhido. Não inventar IDs no LLM a cada retransmissão.

Teste de protocolo sem iniciar agente nem enviar mensagem:

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 integrations/hermes/mcp_server.py
```

## Classificação

O código do Hermes inspecionado (`gateway/platforms/api_server_openai_routes.py`, `_handle_chat_completions`) incorpora mensagens de sistema ao prompt interno, filtra histórico para user/assistant e executa seu próprio agente. Os campos `tools`/`tool_choice` participam do fingerprint, mas não são encaminhados como ferramentas retornáveis ao harness Java; mensagens `tool` tampouco são mantidas nesse histórico.

Portanto, o `HttpAiModel` deste projeto **não deve ser apontado diretamente para essa rota esperando function calling externo**. O agente controlado está em Java: AiModel propõe ferramenta → AgentHarness valida → banco devolve política → modelo propõe triagem → Java valida → IssueGateway encaminha.

O modo real exige provedor/modelo compatível configurado no backend. A integração implantada usa `ai_worker.py` para obter o `CodexAuxiliaryClient` autenticado do Hermes e preservar chamadas de função e resultados de ferramenta no protocolo compatível. Esse worker apenas faz inferência; não executa ferramentas nem recebe comandos arbitrários. O Java continua responsável por consultar políticas, impor limites, validar e encaminhar. As cinco análises reais e seus rastros estão em `docs/ia-real-verificacao.json`.

`private_bridge.py` executa somente esse worker fixo como usuário Hermes. A porta de inferência é loopback; a entrada WhatsApp usa a interface Docker privada, IP de origem único e Bearer específico. Nem a chave do provedor nem a credencial PostgreSQL são entregues ao plugin. Os arquivos privados são gerados e mantidos na VPS.
