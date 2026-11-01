import "appkern-oberflaeche/stil.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/700.css";
import "flag-icons/css/flag-icons.min.css";
import "./stil/nachschlag.css";
import { mount } from "svelte";
import App from "./App.svelte";

mount(App, { target: document.getElementById("app")! });
