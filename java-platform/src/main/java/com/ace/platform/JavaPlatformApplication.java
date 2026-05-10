package com.ace.platform;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import java.sql.Connection;
import java.sql.DriverManager;

@SpringBootApplication
public class JavaPlatformApplication {

	public static void main(String[] args) {
		logDatabasePreflight();
		SpringApplication.run(JavaPlatformApplication.class, args);
	}

	private static void logDatabasePreflight() {
		String jdbcUrl = trimToNull(System.getenv("ACE_DB_URL"));
		String username = trimToNull(System.getenv("ACE_DB_USERNAME"));
		String password = System.getenv("ACE_DB_PASSWORD");
		String profiles = trimToNull(System.getenv("SPRING_PROFILES_ACTIVE"));
		String port = trimToNull(System.getenv("PORT"));

		System.out.println("[ACE-DB-PREFLIGHT] SPRING_PROFILES_ACTIVE=" + valueOrPlaceholder(profiles));
		System.out.println("[ACE-DB-PREFLIGHT] PORT=" + valueOrPlaceholder(port));
		System.out.println("[ACE-DB-PREFLIGHT] ACE_DB_URL=" + valueOrPlaceholder(jdbcUrl));
		System.out.println("[ACE-DB-PREFLIGHT] ACE_DB_USERNAME=" + valueOrPlaceholder(username));
		System.out.println("[ACE-DB-PREFLIGHT] ACE_DB_PASSWORD_PRESENT=" + (password != null && !password.isBlank()));
		System.out.println("[ACE-DB-PREFLIGHT] ACE_DB_PASSWORD_LENGTH=" + (password != null ? password.length() : 0));

		if (jdbcUrl == null || username == null || password == null || password.isBlank()) {
			System.out.println("[ACE-DB-PREFLIGHT] Skipping JDBC connection test because one or more DB env vars are missing.");
			return;
		}

		try (Connection ignored = DriverManager.getConnection(jdbcUrl, username, password)) {
			System.out.println("[ACE-DB-PREFLIGHT] JDBC connection succeeded before Spring startup.");
		} catch (Exception ex) {
			System.out.println("[ACE-DB-PREFLIGHT] JDBC connection failed before Spring startup: " + ex.getClass().getName() + ": " + ex.getMessage());
		}
	}

	private static String trimToNull(String value) {
		if (value == null) {
			return null;
		}
		String trimmed = value.trim();
		return trimmed.isEmpty() ? null : trimmed;
	}

	private static String valueOrPlaceholder(String value) {
		return value != null ? value : "<missing>";
	}

}
