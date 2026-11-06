# Integração Hermes

Perfil dedicado: `kipper-triagem`. Criado em 06/11/2026 no Mac e na VPS, sem clonar config, credenciais, canais, memórias ou skills de outros perfis. A criação do perfil não comprova modelo autenticado, gateway ativo, ponte instalada nem entrada WhatsApp testada.

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

O modo real exige provedor/modelo compatível configurado no backend. Usar Hermes somente para WhatsApp não é apresentado como evidência do agente do desafio; a evidência deve mostrar a chamada real à IA e o rastro `consult_policy` do harness Java. Usar o runtime interno do Hermes para classificar exigiria outro adaptador com auditoria verificável das ferramentas e limites; essa alternativa não foi implementada nem homologada.
