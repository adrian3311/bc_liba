CREATE DATABASE IF NOT EXISTS `__DB_NAME__`
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE `__DB_NAME__`;

CREATE TABLE IF NOT EXISTS `openmeteo_data` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `city` VARCHAR(100) NOT NULL,
    `resolved_city` VARCHAR(255) NULL,
    `station_id` VARCHAR(64) NULL,
    `granularity` ENUM('hourly', 'daily') NOT NULL DEFAULT 'hourly',
    `data_kind` ENUM('prediction', 'reality') NOT NULL DEFAULT 'prediction',
    `forecast_for` DATETIME NOT NULL,
    `latitude` DECIMAL(9, 6) NULL,
    `longitude` DECIMAL(9, 6) NULL,
    `timezone_name` VARCHAR(64) NULL,
    `unit_system` VARCHAR(16) NULL,
    `temperature` DECIMAL(10, 4) NULL,
    `temperature_min` DECIMAL(10, 4) NULL,
    `temperature_max` DECIMAL(10, 4) NULL,
    `temperature_mean` DECIMAL(10, 4) NULL,
    `cloud_cover` DECIMAL(10, 4) NULL,
    `precipitation` DECIMAL(10, 4) NULL,
    `precipitation_sum` DECIMAL(10, 4) NULL,
    `precipitation_probability` DECIMAL(10, 4) NULL,
    `humidity` DECIMAL(10, 4) NULL,
    `wind_speed` DECIMAL(10, 4) NULL,
    `wind_direction` DECIMAL(10, 4) NULL,
    `wind_gusts` DECIMAL(10, 4) NULL,
    `solar_radiation` DECIMAL(12, 4) NULL,
    `uv_index` DECIMAL(10, 4) NULL,
    `visibility` DECIMAL(12, 4) NULL,
    `surface_pressure` DECIMAL(10, 4) NULL,
    `dew_point` DECIMAL(10, 4) NULL,
    `feels_like` DECIMAL(10, 4) NULL,
    `snow` DECIMAL(10, 4) NULL,
    `weather_code` VARCHAR(64) NULL,
    `thunder_probability` DECIMAL(10, 4) NULL,
    `fog` DECIMAL(10, 4) NULL,
    `cape` DECIMAL(12, 4) NULL,
    `evapotranspiration` DECIMAL(10, 4) NULL,
    `vapour_pressure_deficit` DECIMAL(10, 4) NULL,
    `sunshine_duration` DECIMAL(12, 4) NULL,
    `precipitation_hours` DECIMAL(10, 4) NULL,
    `raw_payload` LONGTEXT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_openmeteo_row` (`city`, `forecast_for`, `granularity`, `data_kind`),
    KEY `idx_openmeteo_forecast_for` (`forecast_for`),
    KEY `idx_openmeteo_city_granularity` (`city`, `granularity`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `visualcrossing_data` LIKE `openmeteo_data`;
CREATE TABLE IF NOT EXISTS `met_data` LIKE `openmeteo_data`;
CREATE TABLE IF NOT EXISTS `meteosource_data` LIKE `openmeteo_data`;
CREATE TABLE IF NOT EXISTS `shmu_data` LIKE `openmeteo_data`;
CREATE TABLE IF NOT EXISTS `solcast_data` LIKE `openmeteo_data`;

