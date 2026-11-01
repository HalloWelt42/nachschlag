import "appkern-oberflaeche/stil.css";
import "./stil/nachschlag.css";
import { mount } from "svelte";
import App from "./App.svelte";

mount(App, { target: document.getElementById("app")! });
