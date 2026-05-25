package com.ace.platform.admin;

import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/admin")
public class AdminApiController {

    private final OrganizationRepository orgRepo;
    private final UserRepository userRepo;
    private final PasswordEncoder passwordEncoder;

    public AdminApiController(OrganizationRepository orgRepo, UserRepository userRepo, PasswordEncoder passwordEncoder) {
        this.orgRepo = orgRepo;
        this.userRepo = userRepo;
        this.passwordEncoder = passwordEncoder;
    }

    @GetMapping("/organizations")
    public List<Organization> organizations(Authentication auth) {
        requireAdmin(auth);
        return orgRepo.findAll(Sort.by(Sort.Direction.ASC, "name"));
    }

    @PostMapping("/organizations")
    public Organization createOrganization(@RequestBody Map<String, String> body, Authentication auth) {
        requireAdmin(auth);
        String name = body.getOrDefault("name", "").trim();
        String slug = body.getOrDefault("slug", "").trim().toLowerCase().replaceAll("[^a-z0-9-]+", "-");
        boolean active = Boolean.parseBoolean(body.getOrDefault("active", "true"));
        if (name.isEmpty() || slug.isEmpty()) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Name and slug required");
        if (orgRepo.existsBySlug(slug)) throw new ResponseStatusException(HttpStatus.CONFLICT, "Slug exists");
        return orgRepo.save(new Organization(name, slug, active));
    }

    @GetMapping("/users")
    public List<User> users(Authentication auth) {
        requireAdmin(auth);
        return userRepo.findAllByOrderByUsernameAsc();
    }

    @PostMapping("/users")
    public User createUser(@RequestBody Map<String, String> body, Authentication auth) {
        requireAdmin(auth);
        String username = body.getOrDefault("username", "").trim();
        String email = body.getOrDefault("email", "").trim();
        String password = body.getOrDefault("password", "");
        String role = body.getOrDefault("role", "ORG_USER").toUpperCase();
        Long orgId = body.containsKey("organizationId") ? Long.parseLong(body.get("organizationId")) : null;
        if (username.isEmpty() || email.isEmpty() || password.isEmpty()) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Required fields missing");
        Organization org = orgId != null ? orgRepo.findById(orgId).orElse(null) : null;
        User user = new User(org, username, email, passwordEncoder.encode(password), password, UserRole.valueOf(role), true);
        return userRepo.save(user);
    }

    private void requireAdmin(Authentication auth) {
        if (auth == null || !auth.isAuthenticated()) throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
    }
}
