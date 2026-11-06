package br.com.kipper.triagem.service;

import br.com.kipper.triagem.domain.Models.*;
import br.com.kipper.triagem.domain.DomainException;
import br.com.kipper.triagem.persistence.Store;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;

@Service
public class PolicyService {
    private final Store store;
    public PolicyService(Store store) { this.store=store; }
    public Policy save(String id,PolicyInput input) {
        Team required=switch(input.category()) { case BILLING -> Team.FINANCE; case TECHNICAL -> Team.TECHNICAL; case OTHER -> Team.REVIEW; };
        if(input.team()!=required) throw new DomainException(422,"Equipe incompatível com a categoria do desafio");
        try {
            if(id==null) {
                id=Store.id();
                store.jdbc().update("INSERT INTO policies VALUES (?,?,?,?,?,1,TRUE)",id,input.category().name(),input.subject(),input.rule(),input.team().name());
            } else {
                if(input.expectedVersion()==null) throw new DomainException(400,"Informe expectedVersion");
                if(store.jdbc().update("UPDATE policies SET category=?,subject=?,rule_text=?,team=?,version=version+1,active=TRUE WHERE id=? AND version=?",
                    input.category().name(),input.subject(),input.rule(),input.team().name(),id,input.expectedVersion())!=1)
                    throw new DomainException(409,"Política alterada ou inexistente; recarregue");
            }
        } catch (DuplicateKeyException e) { throw new DomainException(409,"Já existe política para essa categoria; edite ou reative a existente"); }
        return store.policy(input.category());
    }
    public void remove(String id,int version) {
        if(store.jdbc().update("UPDATE policies SET active=FALSE,version=version+1 WHERE id=? AND version=? AND active=TRUE",id,version)!=1)
            throw new DomainException(409,"Política alterada, inexistente ou já removida");
    }
}
