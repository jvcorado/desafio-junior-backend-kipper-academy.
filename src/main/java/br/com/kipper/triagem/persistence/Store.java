package br.com.kipper.triagem.persistence;

import br.com.kipper.triagem.domain.Models.*;
import br.com.kipper.triagem.domain.DomainException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;
import java.time.Instant;
import java.util.*;

@Repository
public class Store {
    private final JdbcTemplate jdbc;
    public JdbcTemplate jdbc() { return jdbc; }
    private final ObjectMapper json;
    public Store(JdbcTemplate jdbc, ObjectMapper json) { this.jdbc = jdbc; this.json = json; }
    public static String now() { return Instant.now().toString(); }
    public static String id() { return UUID.randomUUID().toString(); }
    public String json(Object value) {
        try { return json.writeValueAsString(value); }
        catch (Exception e) { throw new IllegalStateException("Falha de serialização", e); }
    }
    public <T> T read(String value, Class<T> type) {
        try { return json.readValue(value, type); }
        catch (Exception e) { throw new IllegalArgumentException("JSON inválido"); }
    }
    private static <T extends Enum<T>> T optional(Class<T> type, String value) { return value == null ? null : Enum.valueOf(type, value); }
    private final RowMapper<Ticket> ticketMapper = (r, n) -> new Ticket(r.getString("id"), r.getString("source"),
        r.getString("external_ticket_id"), r.getString("customer_id"), r.getString("customer_name"),
        r.getString("whatsapp"), r.getString("message"), r.getString("occurred_at"), r.getString("created_at"),
        r.getString("updated_at"), Status.valueOf(r.getString("status")), optional(Category.class,r.getString("category")),
        optional(Priority.class,r.getString("priority")), optional(Team.class,r.getString("team")), r.getString("explanation"),
        r.getString("external_id"), r.getString("external_url"), r.getString("delivery_adapter"));
    private final RowMapper<Policy> policyMapper = (r, n) -> new Policy(r.getString("id"), Category.valueOf(r.getString("category")),
        r.getString("subject"), r.getString("rule_text"), Team.valueOf(r.getString("team")), r.getInt("version"),r.getBoolean("active"));
    public Ticket ticket(String id) {
        return jdbc.query("SELECT * FROM tickets WHERE id=?", ticketMapper,id).stream().findFirst()
            .orElseThrow(() -> new DomainException(404,"Chamado não encontrado"));
    }
    public List<Ticket> tickets(Team team) {
        return team == null ? jdbc.query("SELECT * FROM tickets ORDER BY created_at DESC",ticketMapper)
            : jdbc.query("SELECT * FROM tickets WHERE team=? ORDER BY created_at DESC",ticketMapper,team.name());
    }
    public List<Policy> policies() { return jdbc.query("SELECT * FROM policies ORDER BY category",policyMapper); }
    public Policy policy(Category category) {
        return jdbc.query("SELECT * FROM policies WHERE category=? AND active=TRUE",policyMapper,category.name())
            .stream().findFirst().orElseThrow(() -> new DomainException(422,"Política ativa não encontrada"));
    }
    public Map<String,Object> detail(String id) {
        return Map.of("ticket",ticket(id),"analyses",jdbc.queryForList("SELECT * FROM analyses WHERE ticket_id=? ORDER BY created_at",id),
            "attempts",jdbc.queryForList("SELECT * FROM delivery_attempts WHERE ticket_id=? ORDER BY created_at",id),
            "actions",jdbc.queryForList("SELECT * FROM ticket_actions WHERE ticket_id=? ORDER BY created_at",id));
    }
    public void insertTicket(String id, Event e) {
        var time = now();
        jdbc.update("INSERT INTO tickets(id,source,external_ticket_id,customer_id,customer_name,whatsapp,message,occurred_at,created_at,updated_at,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            id,e.source(),e.ticketId(),e.customerId(),e.customerName(),e.whatsapp(),e.message(),e.occurredAt().toString(),time,time,Status.RECEIVED.name());
    }
    public boolean claim(String id, Status before, Status after) {
        return jdbc.update("UPDATE tickets SET status=?,updated_at=? WHERE id=? AND status=?",after.name(),now(),id,before.name())==1;
    }
    public void review(String id, String reason) {
        jdbc.update("UPDATE tickets SET status='REVIEW',priority=NULL,team='REVIEW',explanation=?,updated_at=? WHERE id=?",reason,now(),id);
    }
}
