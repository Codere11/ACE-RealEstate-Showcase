package com.ace.platform.config;

import com.ace.platform.auth.BearerTokenAuthenticationFilter;
import com.ace.platform.auth.RoleBasedAuthenticationSuccessHandler;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
public class SecurityConfig {

    private final RoleBasedAuthenticationSuccessHandler roleBasedAuthenticationSuccessHandler;
    private final BearerTokenAuthenticationFilter bearerTokenAuthenticationFilter;

    public SecurityConfig(
        RoleBasedAuthenticationSuccessHandler roleBasedAuthenticationSuccessHandler,
        BearerTokenAuthenticationFilter bearerTokenAuthenticationFilter
    ) {
        this.roleBasedAuthenticationSuccessHandler = roleBasedAuthenticationSuccessHandler;
        this.bearerTokenAuthenticationFilter = bearerTokenAuthenticationFilter;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .cors(cors -> {})
            .csrf(csrf -> csrf.disable())
            .authorizeHttpRequests(auth -> auth
                .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                .requestMatchers(HttpMethod.GET, "/", "/demo", "/*", "/admin", "/admin/dashboard", "/*/dashboard", "/*/survey/*", "/login", "/actuator/health", "/chat-events/poll", "/api/public/**", "/s/**", "/pay/**", "/css/**", "/js/**", "/images/**").permitAll()
                .requestMatchers(HttpMethod.HEAD, "/", "/demo", "/*", "/admin", "/admin/dashboard", "/*/dashboard", "/*/survey/*", "/login", "/actuator/health", "/chat-events/poll", "/api/public/**", "/s/**", "/pay/**", "/css/**", "/js/**", "/images/**").permitAll()
                .requestMatchers(HttpMethod.POST, "/chat", "/chat/", "/chat/stream", "/chat/stream/", "/chat/staff", "/chat/staff/", "/chat/survey/submit", "/api/public/chat", "/api/public/chat/stream", "/api/public/chat/**", "/api/payments/webhooks/stripe", "/pay/**", "/*/survey/*/send", "/api/auth/login").permitAll()
                .requestMatchers("/api/admin/**").hasRole("PLATFORM_ADMIN")
                .anyRequest().authenticated()
            )
            .addFilterBefore(bearerTokenAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)
            .formLogin(form -> form
                .successHandler(roleBasedAuthenticationSuccessHandler)
            )
            .logout(logout -> logout
                .logoutSuccessUrl("/")
            );

        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
