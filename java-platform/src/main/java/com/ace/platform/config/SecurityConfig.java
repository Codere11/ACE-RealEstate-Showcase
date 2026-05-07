package com.ace.platform.config;

import com.ace.platform.auth.RoleBasedAuthenticationSuccessHandler;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {

    private final RoleBasedAuthenticationSuccessHandler roleBasedAuthenticationSuccessHandler;

    public SecurityConfig(RoleBasedAuthenticationSuccessHandler roleBasedAuthenticationSuccessHandler) {
        this.roleBasedAuthenticationSuccessHandler = roleBasedAuthenticationSuccessHandler;
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf
                .ignoringRequestMatchers("/chat", "/chat/", "/chat/staff", "/chat/staff/", "/chat-events/**", "/api/organizations/**")
            )
            .authorizeHttpRequests(auth -> auth
                .requestMatchers(HttpMethod.GET, "/", "/*", "/*/survey/*", "/actuator/health", "/chat-events/poll", "/api/public/organizations/*/leads/*/messages", "/css/**", "/js/**", "/images/**").permitAll()
                .requestMatchers(HttpMethod.HEAD, "/", "/*", "/*/survey/*", "/actuator/health", "/chat-events/poll", "/api/public/organizations/*/leads/*/messages", "/css/**", "/js/**", "/images/**").permitAll()
                .requestMatchers(HttpMethod.POST, "/chat", "/chat/", "/*/survey/*/send").permitAll()
                .requestMatchers("/login").permitAll()
                .requestMatchers("/admin/**").hasRole("PLATFORM_ADMIN")
                .anyRequest().authenticated()
            )
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
