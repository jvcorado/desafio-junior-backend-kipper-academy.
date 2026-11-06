package br.com.kipper.triagem;

import br.com.kipper.triagem.web.LocalAccessFilter;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.*;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.assertj.core.api.Assertions.*;

class WebhookAccessTest {
    @Test void webhookRequiresConfiguredTokenAndMasterRemainsPrivate() throws Exception {
        var filter=new LocalAccessFilter("fake-test-token","127.0.0.1");
        for(boolean authenticated:new boolean[]{false,true}) {
            var request=new MockHttpServletRequest("POST","/api/events");request.setServerName("localhost");request.setContentType("application/json");
            if(authenticated) request.addHeader("Authorization","Bearer fake-test-token");
            var response=new MockHttpServletResponse();var called=new AtomicBoolean();
            filter.doFilter(request,response,(req,res)->called.set(true));
            assertThat(called.get()).isEqualTo(authenticated);if(!authenticated) assertThat(response.getStatus()).isEqualTo(401);
        }
        assertThatThrownBy(()->new LocalAccessFilter("token","0.0.0.0")).isInstanceOf(IllegalArgumentException.class);
    }
}
