package com.ace.platform.admin;

import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import jakarta.transaction.Transactional;
import org.springframework.data.domain.Sort;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import java.security.Principal;

import static com.ace.platform.user.UserRole.PLATFORM_ADMIN;

@Controller
public class AdminController {

    private final OrganizationRepository organizationRepository;
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public AdminController(
        OrganizationRepository organizationRepository,
        UserRepository userRepository,
        PasswordEncoder passwordEncoder
    ) {
        this.organizationRepository = organizationRepository;
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @GetMapping("/admin")
    public String adminRoot() {
        return "redirect:/admin/dashboard";
    }

    @GetMapping("/admin/dashboard")
    public String dashboard(
        @RequestParam(name = "tab", defaultValue = "organizations") String tab,
        Model model,
        Principal principal
    ) {
        model.addAttribute("username", principal != null ? principal.getName() : "admin");
        model.addAttribute("activeTab", tab);
        model.addAttribute("organizations", organizationRepository.findAll(Sort.by(Sort.Direction.ASC, "name")));
        model.addAttribute("users", userRepository.findAllByOrderByUsernameAsc());
        model.addAttribute("roles", UserRole.values());
        model.addAttribute("organizationCount", organizationRepository.count());
        model.addAttribute("userCount", userRepository.count());
        return "admin/dashboard";
    }

    @PostMapping("/admin/organizations")
    public String createOrganization(
        @RequestParam String name,
        @RequestParam String slug,
        @RequestParam(name = "active", defaultValue = "false") boolean active,
        RedirectAttributes redirectAttributes
    ) {
        String normalizedName = name == null ? "" : name.trim();
        String normalizedSlug = normalizeSlug(slug);

        if (normalizedName.isBlank() || normalizedSlug.isBlank()) {
            redirectAttributes.addFlashAttribute("errorMessage", "Organization name and slug are required.");
            return "redirect:/admin/dashboard?tab=create-org";
        }

        if (organizationRepository.existsBySlug(normalizedSlug)) {
            redirectAttributes.addFlashAttribute("errorMessage", "An organization with this slug already exists.");
            return "redirect:/admin/dashboard?tab=create-org";
        }

        Organization organization = organizationRepository.save(new Organization(normalizedName, normalizedSlug, active));
        redirectAttributes.addFlashAttribute("successMessage", "Organization created: " + organization.getName());
        return "redirect:/admin/dashboard?tab=organizations";
    }

    @PostMapping("/admin/organizations/{id}")
    public String updateOrganization(
        @PathVariable Long id,
        @RequestParam String name,
        @RequestParam String slug,
        @RequestParam(name = "active", defaultValue = "false") boolean active,
        RedirectAttributes redirectAttributes
    ) {
        Organization organization = organizationRepository.findById(id).orElse(null);
        if (organization == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "Organization not found.");
            return "redirect:/admin/dashboard?tab=organizations";
        }

        String normalizedName = name == null ? "" : name.trim();
        String normalizedSlug = normalizeSlug(slug);
        if (normalizedName.isBlank() || normalizedSlug.isBlank()) {
            redirectAttributes.addFlashAttribute("errorMessage", "Organization name and slug are required.");
            return "redirect:/admin/dashboard?tab=organizations";
        }

        boolean slugChanged = !organization.getSlug().equalsIgnoreCase(normalizedSlug);
        if (slugChanged && organizationRepository.existsBySlug(normalizedSlug)) {
            redirectAttributes.addFlashAttribute("errorMessage", "Another organization already uses that slug.");
            return "redirect:/admin/dashboard?tab=organizations";
        }

        organization.setName(normalizedName);
        organization.setSlug(normalizedSlug);
        organization.setActive(active);
        organizationRepository.save(organization);

        redirectAttributes.addFlashAttribute("successMessage", "Organization updated: " + organization.getName());
        return "redirect:/admin/dashboard?tab=organizations";
    }

    @PostMapping("/admin/users")
    public String createUser(
        @RequestParam(required = false) Long organizationId,
        @RequestParam String username,
        @RequestParam String email,
        @RequestParam String password,
        @RequestParam UserRole role,
        @RequestParam(name = "active", defaultValue = "true") boolean active,
        RedirectAttributes redirectAttributes
    ) {
        Organization organization = resolveOrganizationForUser(role, organizationId, redirectAttributes, "create-user");
        if (role != PLATFORM_ADMIN && organization == null) {
            return "redirect:/admin/dashboard?tab=create-user";
        }

        String normalizedUsername = username == null ? "" : username.trim();
        String normalizedEmail = email == null ? "" : email.trim().toLowerCase();

        if (normalizedUsername.isBlank() || normalizedEmail.isBlank() || password == null || password.isBlank()) {
            redirectAttributes.addFlashAttribute("errorMessage", "Username, email, password, role, and organization are required for org users.");
            return "redirect:/admin/dashboard?tab=create-user";
        }

        if (userRepository.existsByUsername(normalizedUsername)) {
            redirectAttributes.addFlashAttribute("errorMessage", "Username already exists.");
            return "redirect:/admin/dashboard?tab=create-user";
        }

        if (userRepository.existsByEmail(normalizedEmail)) {
            redirectAttributes.addFlashAttribute("errorMessage", "Email already exists.");
            return "redirect:/admin/dashboard?tab=create-user";
        }

        User user = new User(
            organization,
            normalizedUsername,
            normalizedEmail,
            passwordEncoder.encode(password),
            password,
            role,
            active
        );
        userRepository.save(user);

        String targetLabel = organization != null ? organization.getName() : "platform";
        redirectAttributes.addFlashAttribute("successMessage", "User created for " + targetLabel + ": " + normalizedUsername);
        return "redirect:/admin/dashboard?tab=users";
    }

    @PostMapping("/admin/users/{id}")
    public String updateUser(
        @PathVariable Long id,
        @RequestParam(required = false) Long organizationId,
        @RequestParam String username,
        @RequestParam String email,
        @RequestParam String password,
        @RequestParam UserRole role,
        @RequestParam(name = "active", defaultValue = "false") boolean active,
        RedirectAttributes redirectAttributes
    ) {
        User user = userRepository.findById(id).orElse(null);
        if (user == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "User not found.");
            return "redirect:/admin/dashboard?tab=users";
        }

        String normalizedUsername = username == null ? "" : username.trim();
        String normalizedEmail = email == null ? "" : email.trim().toLowerCase();
        if (normalizedUsername.isBlank() || normalizedEmail.isBlank()) {
            redirectAttributes.addFlashAttribute("errorMessage", "Username and email are required.");
            return "redirect:/admin/dashboard?tab=users";
        }

        if (userRepository.existsByUsernameAndIdNot(normalizedUsername, id)) {
            redirectAttributes.addFlashAttribute("errorMessage", "Another user already uses that username.");
            return "redirect:/admin/dashboard?tab=users";
        }

        if (userRepository.existsByEmailAndIdNot(normalizedEmail, id)) {
            redirectAttributes.addFlashAttribute("errorMessage", "Another user already uses that email.");
            return "redirect:/admin/dashboard?tab=users";
        }

        Organization organization = resolveOrganizationForUser(role, organizationId, redirectAttributes, "users");
        if (role != PLATFORM_ADMIN && organization == null) {
            return "redirect:/admin/dashboard?tab=users";
        }

        user.setOrganization(organization);
        user.setUsername(normalizedUsername);
        user.setEmail(normalizedEmail);
        user.setRole(role);
        user.setActive(active);

        if (password != null && !password.isBlank()) {
            user.setPasswordHash(passwordEncoder.encode(password));
            user.setVisiblePassword(password);
        }

        userRepository.save(user);
        redirectAttributes.addFlashAttribute("successMessage", "User updated: " + user.getUsername());
        return "redirect:/admin/dashboard?tab=users";
    }

    @PostMapping("/admin/users/{id}/delete")
    public String deleteUser(@PathVariable Long id, RedirectAttributes redirectAttributes) {
        User user = userRepository.findById(id).orElse(null);
        if (user == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "User not found.");
            return "redirect:/admin/dashboard?tab=users";
        }
        if ("admin".equalsIgnoreCase(user.getUsername())) {
            redirectAttributes.addFlashAttribute("errorMessage", "The seeded platform admin cannot be deleted from the dashboard right now.");
            return "redirect:/admin/dashboard?tab=users";
        }
        userRepository.delete(user);
        redirectAttributes.addFlashAttribute("successMessage", "User deleted: " + user.getUsername());
        return "redirect:/admin/dashboard?tab=users";
    }

    @PostMapping("/admin/organizations/{id}/delete")
    @Transactional
    public String deleteOrganization(@PathVariable Long id, RedirectAttributes redirectAttributes) {
        Organization organization = organizationRepository.findById(id).orElse(null);
        if (organization == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "Organization not found.");
            return "redirect:/admin/dashboard?tab=organizations";
        }

        long deletedUsers = userRepository.deleteByOrganizationId(id);
        organizationRepository.delete(organization);
        redirectAttributes.addFlashAttribute("successMessage", "Organization deleted: " + organization.getName() + " (removed users: " + deletedUsers + ")");
        return "redirect:/admin/dashboard?tab=organizations";
    }

    private Organization resolveOrganizationForUser(UserRole role, Long organizationId, RedirectAttributes redirectAttributes, String tab) {
        if (role == PLATFORM_ADMIN) {
            return null;
        }
        if (organizationId == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "Organization is required for organization-scoped users.");
            return null;
        }
        Organization organization = organizationRepository.findById(organizationId).orElse(null);
        if (organization == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "Organization not found.");
            return null;
        }
        return organization;
    }

    private String normalizeSlug(String rawSlug) {
        if (rawSlug == null) {
            return "";
        }
        return rawSlug.trim().toLowerCase()
            .replaceAll("[^a-z0-9-]+", "-")
            .replaceAll("-+", "-")
            .replaceAll("^-|-$", "");
    }
}
