package com.ace.platform.tag;

import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;

@RestController
public class TagsController {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final UserRepository userRepository;
    private final String pythonBaseUrl;

    public TagsController(
        ObjectMapper objectMapper,
        UserRepository userRepository,
        @Value("${ace.python-backend-url:http://127.0.0.1:8000}") String pythonBaseUrl
    ) {
        this.httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
        this.objectMapper = objectMapper;
        this.userRepository = userRepository;
        this.pythonBaseUrl = pythonBaseUrl != null ? pythonBaseUrl.replaceAll("/+$", "") : "http://127.0.0.1:8000";
    }

    @GetMapping("/api/tags")
    public TagsPayload getTags(Authentication authentication) {
        requireUser(authentication);
        return forward("GET", null);
    }

    @PutMapping("/api/tags")
    public TagsPayload putTags(@RequestBody TagsPayload payload, Authentication authentication) {
        requireUser(authentication);
        return forward("PUT", payload != null ? payload : new TagsPayload(List.of()));
    }

    private TagsPayload forward(String method, TagsPayload payload) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(pythonBaseUrl + "/api/tags"))
                .timeout(Duration.ofSeconds(20))
                .header("Content-Type", "application/json");

            if ("PUT".equals(method)) {
                builder.PUT(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(payload)));
            } else {
                builder.GET();
            }

            HttpResponse<String> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                HttpStatus status = HttpStatus.resolve(response.statusCode());
                throw new ResponseStatusException(status != null ? status : HttpStatus.BAD_GATEWAY, extractDetail(response.body(), "Tags request failed"));
            }
            return objectMapper.readValue(response.body(), TagsPayload.class);
        } catch (ResponseStatusException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Tags service unavailable", ex);
        }
    }

    private String extractDetail(String body, String fallback) {
        try {
            JsonNode node = objectMapper.readTree(body);
            if (node.hasNonNull("detail")) return node.get("detail").asText();
            if (node.hasNonNull("message")) return node.get("message").asText();
            if (node.hasNonNull("error")) return node.get("error").asText();
        } catch (Exception ignored) {
        }
        return fallback;
    }

    private User requireUser(Authentication authentication) {
        if (authentication == null || authentication.getName() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authentication required");
        }
        return userRepository.findByUsername(authentication.getName())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User not found"));
    }

    public record TagsPayload(List<String> tags) {
    }
}
