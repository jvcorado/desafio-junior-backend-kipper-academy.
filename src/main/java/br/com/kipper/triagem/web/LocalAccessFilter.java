package br.com.kipper.triagem.web;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Set;

/** No account system: expose the master panel only through localhost or a private SSH tunnel. */
@Component
public class LocalAccessFilter extends OncePerRequestFilter {
    private final String webhookToken;
    public LocalAccessFilter(@Value("${triagem.webhook-token}") String webhookToken,@Value("${server.address}") String address) {
        this.webhookToken=webhookToken;
        if(!Set.of("127.0.0.1","::1","localhost").contains(address))
            throw new IllegalArgumentException("Painel sem login deve escutar em loopback; use túnel SSH para acesso remoto");
    }
    protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,FilterChain chain) throws ServletException,IOException {
        response.setHeader("X-Content-Type-Options","nosniff");
        response.setHeader("Referrer-Policy","no-referrer");
        response.setHeader("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
        response.setHeader("Cache-Control","no-store");
        if(request.getRequestURI().startsWith("/api/")) {
            String host=request.getServerName();
            if(!Set.of("localhost","127.0.0.1","0:0:0:0:0:0:0:1","::1").contains(host)) { reject(response,403,"Host não permitido"); return; }
            boolean mutation=!Set.of("GET","HEAD","OPTIONS").contains(request.getMethod());
            if(mutation) {
                String origin=request.getHeader("Origin"), expected=request.getScheme()+"://"+request.getHeader("Host");
                if(origin!=null && !origin.equals(expected)) { reject(response,403,"Origem não permitida"); return; }
                if(request.getContentType()==null || !request.getContentType().toLowerCase().startsWith("application/json")) { reject(response,415,"Envie application/json"); return; }
                if(request.getContentLengthLong()>65536) { reject(response,413,"Evento excede o limite de tamanho"); return; }
            }
            if("/api/events".equals(request.getRequestURI()) && "POST".equals(request.getMethod()) && !webhookToken.isBlank()) {
                String actual=request.getHeader("Authorization");
                if(actual==null || !MessageDigest.isEqual(("Bearer "+webhookToken).getBytes(StandardCharsets.UTF_8),actual.getBytes(StandardCharsets.UTF_8))) {
                    reject(response,401,"Token do webhook inválido"); return;
                }
            }
        }
        chain.doFilter(request,response);
    }
    private void reject(HttpServletResponse response,int status,String message) throws IOException {
        response.setStatus(status); response.setContentType("application/json;charset=UTF-8"); response.getWriter().write("{\"error\":\""+message+"\"}");
    }
}
