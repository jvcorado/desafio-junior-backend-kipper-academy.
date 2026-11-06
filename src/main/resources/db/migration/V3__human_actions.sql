CREATE TABLE ticket_actions (
 id VARCHAR(36) PRIMARY KEY,
 ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id),
 action VARCHAR(30) NOT NULL,
 note VARCHAR(1000) NOT NULL,
 created_at VARCHAR(40) NOT NULL
);
CREATE INDEX actions_ticket ON ticket_actions(ticket_id);
