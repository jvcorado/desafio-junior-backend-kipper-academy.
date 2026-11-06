package br.com.kipper.triagem.service;

import br.com.kipper.triagem.domain.Models.*;
import br.com.kipper.triagem.domain.DomainException;
import br.com.kipper.triagem.persistence.Store;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

@Service
public class ReceptionService {
    private final Store store;
    private final TransactionTemplate tx;
    public ReceptionService(Store store, TransactionTemplate tx) { this.store=store; this.tx=tx; }
    public Receipt receive(Event event) {
        String payload=store.json(event), hash=hash(payload);
        try {
            return tx.execute(s -> insert(event,payload,hash));
        } catch (DuplicateKeyException duplicate) {
            // The unique constraint, rather than a preflight query, arbitrates concurrent producers.
            return duplicate(event,payload,hash);
        }
    }
    private Receipt insert(Event event,String payload,String hash) {
        String id=Store.id();
        store.insertTicket(id,event);
        store.jdbc().update("INSERT INTO inbound_events VALUES (?,?,?,?,?,?)",event.source(),event.eventId(),hash,payload,id,Store.now());
        return new Receipt(id,"CREATED",null);
    }
    private Receipt duplicate(Event event,String payload,String hash) {
        var events=store.jdbc().queryForList("SELECT * FROM inbound_events WHERE source=? AND event_id=?",event.source(),event.eventId());
        String original;
        if (!events.isEmpty()) {
            var first=events.getFirst();
            original=(String)first.get("ticket_id");
            if (hash.equals(first.get("payload_hash"))) return new Receipt(original,"REPEATED",null);
        } else {
            original=store.jdbc().queryForObject("SELECT id FROM tickets WHERE source=? AND external_ticket_id=?",String.class,event.source(),event.ticketId());
        }
        String conflictId=Store.id();
        try {
            store.jdbc().update("INSERT INTO conflicts(id,source,event_id,payload_hash,payload,original_ticket_id,status,created_at) VALUES (?,?,?,?,?,?,'OPEN',?)",
                conflictId,event.source(),event.eventId(),hash,payload,original,Store.now());
        } catch (DuplicateKeyException repeatedConflict) {
            conflictId=store.jdbc().queryForObject("SELECT id FROM conflicts WHERE source=? AND event_id=? AND payload_hash=?",String.class,event.source(),event.eventId(),hash);
        }
        return new Receipt(original,"CONFLICT",conflictId);
    }
    public List<Map<String,Object>> conflicts() { return store.jdbc().queryForList("SELECT * FROM conflicts ORDER BY created_at DESC"); }
    public Receipt release(String id, Resolution resolution) {
        if(resolution.newEventId()==null || resolution.newEventId().isBlank() || resolution.newTicketId()==null || resolution.newTicketId().isBlank())
            throw new DomainException(400,"Informe novos IDs de evento e chamado");
        try {
            return tx.execute(s -> {
                var rows=store.jdbc().queryForList("SELECT * FROM conflicts WHERE id=? FOR UPDATE",id);
                if(rows.isEmpty()) throw new DomainException(404,"Conflito não encontrado");
                var c=rows.getFirst();
                if(!"OPEN".equals(c.get("status"))) throw new DomainException(409,"Conflito já revisado");
                Event e=store.read((String)c.get("payload"),Event.class);
                if(e.eventId().equals(resolution.newEventId()) || e.ticketId().equals(resolution.newTicketId()))
                    throw new DomainException(400,"A liberação exige uma identidade própria");
                Event revised=new Event(e.source(),resolution.newEventId(),resolution.newTicketId(),e.customerId(),e.customerName(),e.whatsapp(),e.message(),e.occurredAt());
                var result=insert(revised,store.json(revised),hash(store.json(revised)));
                store.jdbc().update("UPDATE conflicts SET status='RELEASED',released_ticket_id=?,resolution=? WHERE id=?",result.ticketId(),resolution.note(),id);
                return result;
            });
        } catch (DuplicateKeyException e) { throw new DomainException(409,"Os novos IDs já existem; escolha IDs próprios"); }
    }
    public void dismiss(String id,String note) {
        if(store.jdbc().update("UPDATE conflicts SET status='DISMISSED',resolution=? WHERE id=? AND status='OPEN'",note,id)!=1)
            throw new DomainException(409,"Conflito inexistente ou já revisado");
    }
    private String hash(String payload) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(payload.getBytes(StandardCharsets.UTF_8))); }
        catch(Exception e) { throw new IllegalStateException(e); }
    }
}
