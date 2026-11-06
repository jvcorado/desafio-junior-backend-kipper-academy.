package br.com.kipper.triagem.web;

import br.com.kipper.triagem.domain.Models.*;
import br.com.kipper.triagem.persistence.Store;
import br.com.kipper.triagem.service.*;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController
@RequestMapping("/api")
public class ApiController {
    private final Store store;
    private final ReceptionService reception;
    private final TriageService triage;
    private final PolicyService policies;
    private final String aiMode,deliveryMode;
    public ApiController(Store store,ReceptionService reception,TriageService triage,PolicyService policies,
        @Value("${triagem.ai-mode}") String aiMode,@Value("${triagem.delivery-mode}") String deliveryMode) {
        this.store=store; this.reception=reception; this.triage=triage; this.policies=policies; this.aiMode=aiMode; this.deliveryMode=deliveryMode;
    }
    @GetMapping("/config") public Object config() { return Map.of("aiMode",aiMode,"deliveryMode",deliveryMode); }
    @PostMapping("/events") public ResponseEntity<Receipt> receive(@Valid @RequestBody Event event) {
        Receipt result=reception.receive(event);
        int status=switch(result.outcome()) { case "CREATED" -> 201; case "CONFLICT" -> 409; default -> 200; };
        return ResponseEntity.status(status).body(result);
    }
    @PostMapping("/manual-events") public ResponseEntity<Receipt> manual(@Valid @RequestBody Event event) {
        if(!"panel-test".equals(event.source())) throw new br.com.kipper.triagem.domain.DomainException(400,"A entrada master exige origem panel-test");
        return receive(event);
    }
    @GetMapping("/tickets") public Object tickets(@RequestParam(required=false) Team team) { return store.tickets(team); }
    @GetMapping("/tickets/{id}") public Object ticket(@PathVariable String id) { return store.detail(id); }
    @GetMapping("/tickets/lookup") public Object lookup(@RequestParam String source,@RequestParam String ticketId) {
        var ids=store.jdbc().queryForList("SELECT id FROM tickets WHERE source=? AND external_ticket_id=?",String.class,source,ticketId);
        if(ids.isEmpty()) throw new br.com.kipper.triagem.domain.DomainException(404,"Chamado não encontrado");
        return store.detail(ids.getFirst());
    }
    @PostMapping("/tickets/{id}/process") public Object process(@PathVariable String id) { return triage.process(id); }
    @PostMapping("/tickets/{id}/retry") public Object retry(@PathVariable String id) { return triage.retry(id); }
    @PostMapping("/tickets/{id}/reconcile") public Object reconcile(@PathVariable String id) { return triage.reconcile(id); }
    @PostMapping("/tickets/{id}/reanalyze") public Object reanalyze(@PathVariable String id,@Valid @RequestBody Note note) { return triage.reanalyze(id,note.note()); }
    @PostMapping("/tickets/{id}/recover") public Object recover(@PathVariable String id,@Valid @RequestBody Note note) { return triage.recover(id,note.note()); }
    @PostMapping("/tickets/{id}/close") public Object close(@PathVariable String id,@Valid @RequestBody Note note) { return triage.close(id,note.note()); }
    @GetMapping("/policies") public Object policies() { return store.policies(); }
    @PostMapping("/policies") public Object createPolicy(@Valid @RequestBody PolicyInput input) { return policies.save(null,input); }
    @PutMapping("/policies/{id}") public Object updatePolicy(@PathVariable String id,@Valid @RequestBody PolicyInput input) { return policies.save(id,input); }
    @DeleteMapping("/policies/{id}") public void removePolicy(@PathVariable String id,@RequestParam int version) { policies.remove(id,version); }
    @GetMapping("/conflicts") public Object conflicts() { return reception.conflicts(); }
    @PostMapping("/conflicts/{id}/release") public Object release(@PathVariable String id,@Valid @RequestBody Resolution resolution) { return reception.release(id,resolution); }
    @PostMapping("/conflicts/{id}/dismiss") public void dismiss(@PathVariable String id,@Valid @RequestBody Note note) { reception.dismiss(id,note.note()); }
}
