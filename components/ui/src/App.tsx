import {
  Alert,
  Button,
  Form,
  FormGroup,
  Grid,
  GridItem,
  Masthead,
  MastheadMain,
  Page,
  PageSection,
  Spinner,
  Title,
} from "@patternfly/react-core";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { postChat } from "./api";
import countries from "./data/countries.json";
import { ReportView } from "./report-view";
import {
  CITIZENSHIP_OPTIONS,
  Country,
  SEASONS,
  countryFromTarget,
  seasonFromDate,
  toggleCountry,
  tripPayload,
  validateTrip,
} from "./trip";

type Message = { role: "user" | "assistant"; content: string };

const catalog = countries as Country[];

export function App() {
  const [svg, setSvg] = useState("");
  const [route, setRoute] = useState<Country[]>([]);
  const [originCode, setOriginCode] = useState("");
  const [citizenshipStatus, setCitizenshipStatus] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [season, setSeason] = useState("");
  const [prompt, setPrompt] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [tripId, setTripId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const mapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/world.svg")
      .then((response) => response.text())
      .then((text) => setSvg(text.replace(/<\?xml[^>]*>/, "")))
      .catch(() => setError("The world map could not be loaded."));
  }, []);

  useEffect(() => {
    const root = mapRef.current;
    if (!root) {
      return;
    }
    root.querySelectorAll(".country").forEach((node) => {
      const code = node.getAttribute("data-iso");
      node.classList.toggle("selected", route.some((country) => country.code === code));
    });
  }, [route, svg]);

  const input = useMemo(
    () => ({
      countries: route,
      startDate,
      endDate,
      season,
      originCode,
      citizenshipStatus,
      prompt,
    }),
    [route, startDate, endDate, season, originCode, citizenshipStatus, prompt],
  );

  function selectCountry(code: string) {
    const country = catalog.find((item) => item.code === code);
    if (!country) {
      return;
    }
    setRoute((current) => toggleCountry(current, country));
  }

  async function generate(event: FormEvent) {
    event.preventDefault();
    const errors = validateTrip(input);
    if (errors.length > 0) {
      setError(errors.join(" "));
      return;
    }
    setError("");
    setBusy(true);
    const nextTripId = `trip-${Date.now()}`;
    setMessages((current) => [...current, { role: "user", content: prompt.trim() }]);
    try {
      const report = await postChat({ trip: tripPayload(input, catalog, nextTripId) });
      setTripId(report.trip_id);
      setMessages((current) => [...current, { role: "assistant", content: report.content }]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The report could not be generated.");
    } finally {
      setBusy(false);
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    if (!tripId || !followUp.trim()) {
      setError("Generate a report before asking a follow-up question.");
      return;
    }
    const question = followUp.trim();
    setFollowUp("");
    setError("");
    setBusy(true);
    setMessages((current) => [...current, { role: "user", content: question }]);
    try {
      const answer = await postChat({ trip_id: tripId, message: question });
      setMessages((current) => [...current, { role: "assistant", content: answer.content }]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The follow-up could not be answered.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page
      masthead={
        <Masthead>
          <MastheadMain>
            <Title headingLevel="h1">FlyFish</Title>
          </MastheadMain>
        </Masthead>
      }
    >
      <PageSection>
        <p>
          Choose countries in the order you will travel, then ask for a report. Follow-up questions are answered from
          that report.
        </p>
        <Grid hasGutter style={{ marginTop: "1rem" }}>
          <GridItem md={7}>
            <div
              className="flyfish-map"
              ref={mapRef}
              onClick={(event) => {
                const code = countryFromTarget(event.target);
                if (code) {
                  selectCountry(code);
                }
              }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
            <div className="flyfish-route" aria-label="Selected route">
              {route.length === 0 ? <span>No countries selected.</span> : null}
              {route.map((country, index) => (
                <Button key={country.code} variant="secondary" onClick={() => selectCountry(country.code)}>
                  {index + 1}. {country.name}
                </Button>
              ))}
            </div>
            <Form onSubmit={generate} style={{ marginTop: "1rem" }}>
              <FormGroup label="Add a country that is hard to click" fieldId="add-country">
                <select
                  id="add-country"
                  value=""
                  onChange={(event) => {
                    if (event.target.value) {
                      selectCountry(event.target.value);
                    }
                  }}
                >
                  <option value="">Select a country</option>
                  {catalog.map((country) => (
                    <option key={country.code} value={country.code}>
                      {country.name}
                    </option>
                  ))}
                </select>
              </FormGroup>
              <FormGroup label="Country of origin" fieldId="origin" isRequired>
                <select id="origin" value={originCode} onChange={(event) => setOriginCode(event.target.value)} required>
                  <option value="">Select origin</option>
                  {catalog.map((country) => (
                    <option key={country.code} value={country.code}>
                      {country.name}
                    </option>
                  ))}
                </select>
              </FormGroup>
              <FormGroup label="Citizenship status" fieldId="citizenship" isRequired>
                <select
                  id="citizenship"
                  value={citizenshipStatus}
                  onChange={(event) => setCitizenshipStatus(event.target.value)}
                  required
                >
                  <option value="">Select status</option>
                  {CITIZENSHIP_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </FormGroup>
              <FormGroup label="Start date" fieldId="start" isRequired>
                <input
                  id="start"
                  type="date"
                  value={startDate}
                  onChange={(event) => {
                    setStartDate(event.target.value);
                    if (!season && event.target.value) {
                      setSeason(seasonFromDate(event.target.value));
                    }
                  }}
                  required
                />
              </FormGroup>
              <FormGroup label="End date" fieldId="end" isRequired>
                <input id="end" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} required />
              </FormGroup>
              <FormGroup label="Time of year" fieldId="season" isRequired>
                <select id="season" value={season} onChange={(event) => setSeason(event.target.value)} required>
                  <option value="">Select time of year</option>
                  {SEASONS.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </FormGroup>
              <FormGroup label="Prompt" fieldId="prompt" isRequired>
                <textarea
                  id="prompt"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  rows={4}
                  required
                />
              </FormGroup>
              <Button type="submit" variant="primary" isDisabled={busy}>
                Generate report
              </Button>
            </Form>
          </GridItem>
          <GridItem md={5}>
            <div className="flyfish-chat">
              <Title headingLevel="h2">Report and questions</Title>
              {error ? <Alert variant="danger" title={error} isInline /> : null}
              {busy ? <Spinner size="md" aria-label="Waiting for the response agent" /> : null}
              <div className="flyfish-transcript" aria-live="polite">
                {messages.map((message, index) => (
                  <article key={`${message.role}-${index}`} className="flyfish-message">
                    <strong>{message.role === "user" ? "You" : "FlyFish"}</strong>
                    {message.role === "assistant" ? (
                      <ReportView text={message.content} />
                    ) : (
                      <p>{message.content}</p>
                    )}
                  </article>
                ))}
              </div>
              <Form onSubmit={ask}>
                <FormGroup label="Ask about this report" fieldId="follow-up">
                  <textarea
                    id="follow-up"
                    value={followUp}
                    onChange={(event) => setFollowUp(event.target.value)}
                    rows={3}
                    disabled={!tripId || busy}
                  />
                </FormGroup>
                <Button type="submit" variant="secondary" isDisabled={!tripId || busy}>
                  Ask
                </Button>
              </Form>
            </div>
          </GridItem>
        </Grid>
      </PageSection>
    </Page>
  );
}
