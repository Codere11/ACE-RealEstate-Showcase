package com.ace.platform.qualifier;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;

@Component
public class PythonQualifierRuntimeClient {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String baseUrl;

    public PythonQualifierRuntimeClient(ObjectMapper objectMapper, @Value("${ace.python-backend-url:http://127.0.0.1:8000}") String baseUrl) {
        this.httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
        this.objectMapper = objectMapper;
        this.baseUrl = baseUrl != null ? baseUrl.replaceAll("/+$", "") : "http://127.0.0.1:8000";
    }

    public RuntimeResponse evaluate(RuntimeRequest request) {
        try {
            String body = objectMapper.writeValueAsString(request);
            HttpRequest httpRequest = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/api/internal/qualifier-runtime/evaluate"))
                .timeout(Duration.ofSeconds(40))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
            HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("Python qualifier runtime returned status " + response.statusCode() + ": " + response.body());
            }
            return objectMapper.readValue(response.body(), RuntimeResponse.class);
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to call Python qualifier runtime", ex);
        }
    }

    public record RuntimeRequest(
        String sid,
        String message,
        Map<String, Object> qualifier,
        @JsonProperty("recent_messages") List<Map<String, String>> recentMessages,
        @JsonProperty("existing_profile") Map<String, Object> existingProfile
    ) {
    }

    public record RuntimeResponse(
        String reply,
        Map<String, Object> profile,
        @JsonProperty("field_confidence") Map<String, Double> fieldConfidence,
        @JsonProperty("qualification_score") int qualificationScore,
        @JsonProperty("qualification_band") String qualificationBand,
        @JsonProperty("confidence_overall") double confidenceOverall,
        String reasoning,
        @JsonProperty("recommended_next_action") String recommendedNextAction,
        @JsonProperty("missing_fields") List<String> missingFields,
        @JsonProperty("takeover_eligible") boolean takeoverEligible,
        @JsonProperty("video_offer_eligible") boolean videoOfferEligible,
        @JsonProperty("model_name") String modelName
    ) {
        public Map<String, Object> safeProfile() {
            return profile != null ? profile : Map.of();
        }

        public List<String> safeMissingFields() {
            return missingFields != null ? missingFields : List.of();
        }
    }
}
