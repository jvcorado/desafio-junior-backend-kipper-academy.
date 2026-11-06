CREATE TABLE tickets (
 id VARCHAR(36) PRIMARY KEY,
 source VARCHAR(60) NOT NULL,
 external_ticket_id VARCHAR(160) NOT NULL,
 customer_id VARCHAR(160) NOT NULL,
 customer_name VARCHAR(120) NOT NULL,
 whatsapp VARCHAR(20) NOT NULL,
 message TEXT NOT NULL,
 occurred_at VARCHAR(40) NOT NULL,
 created_at VARCHAR(40) NOT NULL,
 updated_at VARCHAR(40) NOT NULL,
 status VARCHAR(40) NOT NULL,
 category VARCHAR(20), priority VARCHAR(20), team VARCHAR(20),
 explanation VARCHAR(1000), external_id VARCHAR(160), external_url VARCHAR(1000),
 delivery_adapter VARCHAR(20),
 UNIQUE(source, external_ticket_id)
);
CREATE TABLE inbound_events (
 source VARCHAR(60) NOT NULL,
 event_id VARCHAR(160) NOT NULL,
 payload_hash VARCHAR(64) NOT NULL,
 payload TEXT NOT NULL,
 ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
 created_at VARCHAR(40) NOT NULL,
 PRIMARY KEY(source, event_id)
);
CREATE TABLE conflicts (
 id VARCHAR(36) PRIMARY KEY,
 source VARCHAR(60) NOT NULL,
 event_id VARCHAR(160) NOT NULL,
 payload_hash VARCHAR(64) NOT NULL,
 payload TEXT NOT NULL,
 original_ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
 status VARCHAR(20) NOT NULL,
 resolution VARCHAR(1000),
 released_ticket_id VARCHAR(36) REFERENCES tickets(id),
 created_at VARCHAR(40) NOT NULL,
 UNIQUE(source, event_id, payload_hash)
);
CREATE TABLE policies (
 id VARCHAR(36) PRIMARY KEY,
 category VARCHAR(20) NOT NULL UNIQUE,
 subject VARCHAR(160) NOT NULL,
 rule_text VARCHAR(3000) NOT NULL,
 team VARCHAR(20) NOT NULL,
 version INTEGER NOT NULL,
 active BOOLEAN NOT NULL
);
CREATE TABLE analyses (
 id VARCHAR(36) PRIMARY KEY,
 ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
 created_at VARCHAR(40) NOT NULL,
 adapter VARCHAR(20) NOT NULL,
 proposal TEXT,
 policy_snapshots TEXT NOT NULL,
 tool_trace TEXT NOT NULL,
 valid BOOLEAN NOT NULL,
 reason VARCHAR(1000) NOT NULL
);
CREATE TABLE delivery_attempts (
 id VARCHAR(36) PRIMARY KEY,
 ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
 created_at VARCHAR(40) NOT NULL,
 adapter VARCHAR(20) NOT NULL,
 outcome VARCHAR(30) NOT NULL,
 detail VARCHAR(1000) NOT NULL,
 external_id VARCHAR(160), external_url VARCHAR(1000)
);
CREATE INDEX tickets_status ON tickets(status);
CREATE INDEX analyses_ticket ON analyses(ticket_id);
CREATE INDEX attempts_ticket ON delivery_attempts(ticket_id);
