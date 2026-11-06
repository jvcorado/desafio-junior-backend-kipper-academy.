# Contrato HTTP v1

Base local: `http://localhost:8080/api`. Requisições de escrita exigem `Content-Type: application/json`, inclusive ações com corpo `{}` e DELETE. Erros usam `{"error":"explicação","fields":[...]}`; 409 de entrada é uma resposta própria com `outcome=CONFLICT`, não descarte da mensagem. CORS não está habilitado; escritas originadas de outros sites são recusadas.

| Método e rota | Comportamento |
| --- | --- |
| `POST /events` | Evento completo; 201 criado, 200 repetido, 409 conflito preservado; 400 inválido. Bearer se `WEBHOOK_TOKEN` estiver definido. |
| `POST /manual-events` | Mesma validação, criação pelo painel master privado; origem obrigatória `panel-test`. |
| `GET /tickets?team=FINANCE` | Lista; filtro opcional FINANCE, TECHNICAL ou REVIEW. Chamados novos ainda não possuem equipe. |
| `GET /tickets/{uuid}` | Chamado, análises com snapshots/rastro, tentativas e ações humanas. |
| `GET /tickets/lookup?source=...&ticketId=...` | Consulta pelo identificador externo do atendimento. |
| `POST /tickets/{uuid}/process` | Somente RECEIVED; analisa e encaminha se válido. Processamento síncrono, separado da recepção. |
| `POST /tickets/{uuid}/retry` | Somente DELIVERY_FAILED, com mesmo adaptador. Nunca aceita SENDING/DELIVERY_UNKNOWN. |
| `POST /tickets/{uuid}/reconcile` | Consulta o destino, sem criar; somente SENDING/DELIVERY_UNKNOWN e mesmo adaptador. |
| `POST /tickets/{uuid}/reanalyze` | Somente REVIEW; exige `{"note":"motivo"}`. Repete análise da mensagem original; não inventa informações adicionais. |
| `POST /tickets/{uuid}/recover` | PROCESSING parado por pelo menos 15 min; exige nota e move para revisão. |
| `POST /tickets/{uuid}/close` | Somente FORWARDED; exige nota e encerra por decisão humana. |
| `GET /policies` | Inclui ativas e desativadas. |
| `POST /policies` | Nova categoria ainda não cadastrada. |
| `PUT /policies/{id}` | Edita/reativa; exige versão atual em `expectedVersion`. |
| `DELETE /policies/{id}?version=1` | Desativa com controle de versão. Não apaga histórico. |
| `GET /conflicts` | Inclui payload preservado, original, liberação e justificativa. |
| `POST /conflicts/{id}/release` | `{"note":"outro atendimento confirmado","newEventId":"evt-novo","newTicketId":"ticket-novo"}`. IDs próprios, uma única liberação transacional. |
| `POST /conflicts/{id}/dismiss` | `{"note":"justificativa da revisão"}`; mantém o registro. |
| `GET /config` | Modos dos adaptadores, sem credenciais. |

Evento (todos os campos obrigatórios): `source` (1–60, alfanumérico, hífen/underscore), `eventId` (1–160), `ticketId` (1–160), `customerId` (1–160), `customerName` (1–120), `whatsapp` (E.164 `+` e 8–15 dígitos), `message` (1–12000), `occurredAt` (ISO-8601 com timezone). Campos extras são recusados. O mapeamento do transporte WhatsApp ainda exige IDs e horário confiáveis; não há suposição de um formato nativo Hermes já homologado.

Política: `category` BILLING/TECHNICAL/OTHER, `subject` (até 160), `rule` (até 3000), `team` FINANCE/TECHNICAL/REVIEW, `expectedVersion` (na edição). Uma categoria possui uma política; para reativar, edite a existente. O backend mantém o roteamento obrigatório do desafio mesmo se o texto administrativo sugerir algo contrário.

Leitura/escrita administrativa não tem autenticação de usuário: depende de acesso privado em loopback/túnel. A proteção do webhook não substitui esse isolamento. O endpoint manual é deliberadamente parte da administração privada e não deve ser exposto por um proxy de entrada WhatsApp.
