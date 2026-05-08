package com.ace.platform.user;

import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@RestController
public class UsersApiController {

    private final UserRepository userRepository;
    private final OrganizationRepository organizationRepository;
    private final PasswordEncoder passwordEncoder;

    public UsersApiController(UserRepository userRepository, OrganizationRepository organizationRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.organizationRepository = organizationRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @GetMapping("/api/organizations/{orgId}/users")
    public List<UserResponse> list(@PathVariable Long orgId, Authentication authentication) {
        User currentUser = requireUser(authentication);
        requireOrgAdminAccess(currentUser, orgId);
        return userRepository.findByOrganizationIdOrderByUsernameAsc(orgId).stream().map(UserResponse::from).toList();
    }

    @PostMapping("/api/organizations/{orgId}/users")
    public UserResponse create(@PathVariable Long orgId, @RequestBody UserUpsertRequest request, Authentication authentication) {
        User currentUser = requireUser(authentication);
        requireOrgAdminAccess(currentUser, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));

        String username = requireText(request.username(), "username");
        String email = requireText(request.email(), "email");
        String password = requireText(request.password(), "password");
        if (userRepository.existsByUsername(username)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Username already exists");
        }
        if (userRepository.existsByEmail(email)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email already exists");
        }

        User user = new User(
            organization,
            username,
            email,
            passwordEncoder.encode(password),
            password,
            modelRole(request.role()),
            request.isActive() == null || request.isActive()
        );
        return UserResponse.from(userRepository.save(user));
    }

    @PutMapping("/api/organizations/{orgId}/users/{userId}")
    public UserResponse update(@PathVariable Long orgId, @PathVariable Long userId, @RequestBody UserUpsertRequest request, Authentication authentication) {
        User currentUser = requireUser(authentication);
        requireOrgAdminAccess(currentUser, orgId);
        User user = userRepository.findById(userId)
            .filter(item -> item.getOrganization() != null && orgId.equals(item.getOrganization().getId()))
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));

        if (request.username() != null && !request.username().isBlank()) {
            String username = request.username().trim();
            if (userRepository.existsByUsernameAndIdNot(username, userId)) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Username already exists");
            }
            user.setUsername(username);
        }
        if (request.email() != null && !request.email().isBlank()) {
            String email = request.email().trim();
            if (userRepository.existsByEmailAndIdNot(email, userId)) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Email already exists");
            }
            user.setEmail(email);
        }
        if (request.password() != null && !request.password().isBlank()) {
            user.setPasswordHash(passwordEncoder.encode(request.password().trim()));
            user.setVisiblePassword(request.password().trim());
        }
        if (request.role() != null && !request.role().isBlank()) {
            user.setRole(modelRole(request.role()));
        }
        if (request.isActive() != null) {
            user.setActive(request.isActive());
        }
        return UserResponse.from(userRepository.save(user));
    }

    @DeleteMapping("/api/organizations/{orgId}/users/{userId}")
    public Map<String, Object> delete(@PathVariable Long orgId, @PathVariable Long userId, Authentication authentication) {
        User currentUser = requireUser(authentication);
        requireOrgAdminAccess(currentUser, orgId);
        User user = userRepository.findById(userId)
            .filter(item -> item.getOrganization() != null && orgId.equals(item.getOrganization().getId()))
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));
        userRepository.delete(user);
        return Map.of("ok", true, "userId", userId);
    }

    private User requireUser(Authentication authentication) {
        if (authentication == null || authentication.getName() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authentication required");
        }
        return userRepository.findByUsername(authentication.getName())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User not found"));
    }

    private void requireOrgAdminAccess(User user, Long orgId) {
        boolean platformAdmin = user.getRole() == UserRole.PLATFORM_ADMIN;
        boolean orgAdmin = user.getRole() == UserRole.ORG_ADMIN && user.getOrganization() != null && orgId.equals(user.getOrganization().getId());
        if (!platformAdmin && !orgAdmin) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This user cannot manage the requested organization");
        }
    }

    private String requireText(String value, String label) {
        if (value == null || value.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Missing " + label);
        }
        return value.trim();
    }

    private UserRole modelRole(String role) {
        String normalized = role == null ? "org_user" : role.trim().toLowerCase();
        return switch (normalized) {
            case "platform_admin" -> UserRole.PLATFORM_ADMIN;
            case "org_admin" -> UserRole.ORG_ADMIN;
            case "manager", "org_user" -> UserRole.MANAGER;
            default -> throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid role");
        };
    }

    public record UserUpsertRequest(String username, String email, String password, String role, @JsonProperty("is_active") Boolean isActive) {
    }

    public record UserResponse(
        Long id,
        String username,
        String email,
        String role,
        @JsonProperty("organization_id") Long organizationId,
        @JsonProperty("organization_slug") String organizationSlug,
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
                user.isActive(),
                user.getCreatedAt(),
                null
            );
        }
    }
}
