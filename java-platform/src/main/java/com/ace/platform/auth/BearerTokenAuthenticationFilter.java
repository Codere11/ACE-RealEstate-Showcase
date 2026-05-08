package com.ace.platform.auth;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Component
public class BearerTokenAuthenticationFilter extends OncePerRequestFilter {

    private final AceJwtService aceJwtService;

    public BearerTokenAuthenticationFilter(AceJwtService aceJwtService) {
        this.aceJwtService = aceJwtService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain) throws ServletException, IOException {
        if (SecurityContextHolder.getContext().getAuthentication() == null) {
            String header = request.getHeader("Authorization");
            if (header != null && header.regionMatches(true, 0, "Bearer ", 0, 7)) {
                String token = header.substring(7).trim();
                Optional<Map<String, Object>> claims = aceJwtService.verify(token);
                if (claims.isPresent()) {
                    String subject = stringClaim(claims.get(), "sub");
                    if (subject != null && !subject.isBlank()) {
                        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                            subject,
                            token,
                            authorities(claims.get())
                        );
                        authentication.setDetails(claims.get());
                        SecurityContextHolder.getContext().setAuthentication(authentication);
                    }
                }
            }
        }
        filterChain.doFilter(request, response);
    }

    private List<SimpleGrantedAuthority> authorities(Map<String, Object> claims) {
        List<SimpleGrantedAuthority> out = new ArrayList<>();
        String role = stringClaim(claims, "role");
        if (role == null || role.isBlank()) return out;
        switch (role.toLowerCase()) {
            case "platform_admin" -> out.add(new SimpleGrantedAuthority("ROLE_PLATFORM_ADMIN"));
            case "org_admin" -> out.add(new SimpleGrantedAuthority("ROLE_ORG_ADMIN"));
            case "manager", "org_user" -> out.add(new SimpleGrantedAuthority("ROLE_MANAGER"));
            default -> {
            }
        }
        return out;
    }

    private String stringClaim(Map<String, Object> claims, String key) {
        Object value = claims.get(key);
        return value != null ? String.valueOf(value) : null;
    }
}
