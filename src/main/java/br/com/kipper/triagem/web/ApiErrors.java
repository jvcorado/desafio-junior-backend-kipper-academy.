package br.com.kipper.triagem.web;

import br.com.kipper.triagem.domain.DomainException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.dao.DataAccessException;
import java.util.*;

@RestControllerAdvice
public class ApiErrors {
    @ExceptionHandler(DomainException.class) public ResponseEntity<?> domain(DomainException e) { return ResponseEntity.status(e.status()).body(Map.of("error",e.getMessage())); }
    @ExceptionHandler(MethodArgumentNotValidException.class) public ResponseEntity<?> validation(MethodArgumentNotValidException e) {
        var fields=e.getBindingResult().getFieldErrors().stream().map(f -> f.getField()+": "+f.getDefaultMessage()).toList();
        return ResponseEntity.badRequest().body(Map.of("error","Revise os dados obrigatórios","fields",fields));
    }
    @ExceptionHandler({HttpMessageNotReadableException.class,MethodArgumentTypeMismatchException.class}) public ResponseEntity<?> invalid(Exception e) {
        return ResponseEntity.badRequest().body(Map.of("error","JSON, data ou opção inválida. Confira o contrato da API."));
    }
    @ExceptionHandler(DataAccessException.class) public ResponseEntity<?> database(DataAccessException e) {
        return ResponseEntity.status(503).body(Map.of("error","Persistência indisponível; consulte o estado do evento antes de repetir."));
    }
}
