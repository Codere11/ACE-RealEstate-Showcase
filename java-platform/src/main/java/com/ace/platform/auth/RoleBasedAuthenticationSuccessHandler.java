package com.ace.platform.auth;

import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.Authentication;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;

@Component
public class RoleBasedAuthenticationSuccessHandler implements AuthenticationSuccessHandler {

    private final UserRepository userRepository;

    public RoleBasedAuthenticationSuccessHandler(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    @Transactional(readOnly = true)
    public void onAuthenticationSuccess(HttpServletRequest request, HttpServletResponse response, Authentication authentication) throws IOException, ServletException {
        User user = userRepository.findByUsername(authentication.getName()).orElse(null);

        if (user == null) {
            response.sendRedirect("/");
            return;
        }

        if (user.getRole() == UserRole.PLATFORM_ADMIN) {
            response.sendRedirect("/admin/dashboard");
            return;
        }

        if (user.getOrganization() != null && user.getOrganization().getSlug() != null && !user.getOrganization().getSlug().isBlank()) {
            response.sendRedirect("/" + user.getOrganization().getSlug() + "/dashboard");
            return;
        }

        response.sendRedirect("/");
    }
}
