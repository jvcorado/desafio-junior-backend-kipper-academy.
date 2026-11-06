package br.com.kipper.triagem.delivery;

import br.com.kipper.triagem.domain.Models.Ticket;

/** Replacing this adapter never changes triage rules or orchestration. */
public interface IssueGateway {
    enum Outcome { CONFIRMED, REJECTED, UNKNOWN }
    record Result(Outcome outcome,String externalId,String url,String detail) {
        public static Result unknown(String reason) { return new Result(Outcome.UNKNOWN,null,null,reason); }
    }
    Result create(Ticket ticket);
    Result find(Ticket ticket);
    String name();
}
