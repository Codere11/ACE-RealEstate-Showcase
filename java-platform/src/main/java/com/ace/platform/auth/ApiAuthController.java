package com.ace.platform.auth;

import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
public class ApiAuthController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final AceJwtService aceJwtService;

    public ApiAuthController(UserRepository userRepository, PasswordEncoder passwordEncoder, AceJwtService aceJwtService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.aceJwtService = aceJwtService;
    }

    @PostMapping("/api/auth/login")
    public LoginResponse login(@RequestBody LoginRequest request) {
        User user = userRepository.findByUsername(request.username())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials"));
        if (!user.isActive() || request.password() == null || !passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials");
        }

        Map<String, Object> claims = new LinkedHashMap<>();
        claims.put("sub", user.getUsername());
        claims.put("user_id", user.getId());
        claims.put("role", apiRole(user.getRole()));
        claims.put("organization_id", user.getOrganization() != null ? user.getOrganization().getId() : null);
        claims.put("organization_slug", user.getOrganization() != null ? user.getOrganization().getSlug() : null);
        claims.put("tenant_id", user.getOrganization() != null ? user.getOrganization().getId() : null);
        claims.put("tenant_slug", user.getOrganization() != null ? user.getOrganization().getSlug() : null);

        return new LoginResponse(aceJwtService.createToken(claims), UserResponse.from(user));
    }

    @GetMapping("/api/auth/me")
    public MeResponse me(Authentication authentication) {
        if (authentication == null || authentication.getName() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Missing token");
        }
        User user = userRepository.findByUsername(authentication.getName())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User not found"));
        if (!user.isActive()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User inactive");
        }
        return new MeResponse(UserResponse.from(user));
    }

    private String apiRole(UserRole role) {
        return switch (role) {
            case PLATFORM_ADMIN -> "platform_admin";
            case ORG_ADMIN -> "org_admin";
            case MANAGER -> "org_user";
        };
    }

    public record LoginRequest(String username, String password) {
    }

    public record LoginResponse(String token, UserResponse user) {
    }

    public record MeResponse(UserResponse user) {
    }

    public record UserResponse(
        Long id,
        String username,
        String email,
        String role,
        @JsonProperty("organization_id") Long organizationId,
        @JsonProperty("organization_slug") String organizationSlug,
        @JsonProperty("avatar_url") String avatarUrl,
        @JsonProperty("is_active") boolean isActive,
        @JsonProperty("created_at") Instant createdAt,
        @JsonProperty("last_login") Instant lastLogin
    ) {
        static UserResponse from(User user) {
            return new UserResponse(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                switch (user.getRole()) {
                    case PLATFORM_ADMIN -> "platform_admin";
                    case ORG_ADMIN -> "org_admin";
                    case MANAGER -> "org_user";
                },
                user.getOrganization() != null ? user.getOrganization().getId() : null,
                user.getOrganization() != null ? user.getOrganization().getSlug() : null,
                null,
                user.isActive(),
                user.getCreatedAt(),
                null
            );
        }
    }
}
