FROM maven:3.9.11-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn -B dependency:go-offline
COPY src ./src
RUN mvn -B -DskipTests package
FROM eclipse-temurin:21-jre
RUN useradd --system --uid 10001 --create-home triagem
WORKDIR /app
COPY --from=build --chown=triagem /app/target/triagem-suporte-1.0.0.jar app.jar
USER triagem
ENTRYPOINT ["java","-jar","app.jar"]
