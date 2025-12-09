from socket import gethostname
from typing import List, Optional
from dataclasses import dataclass
from enum import StrEnum, IntEnum, Enum

import dash
from dash import html, Input, Output, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from .fixture_manager import FixtureManager
from .fixture_definitions import FixturePatch
from .sacn_manager import sACNmanager
from .config_manager import ConfigManager
from .gpio_rpi import GPIO
from .project_logger import getLastLogEntries
from .misc import APPNAME


class DmxMapSpec(Enum):
    """Defines spec for Dmx HeatMap visualization for desktop and mobile"""

    DESKTOP = (64, 8, 210)  # columns, rows, height
    MOBILE = (16, 32, 650)

    @property
    def cols(self) -> int:
        return self.value[0]

    @property
    def rows(self) -> int:
        return self.value[1]

    @property
    def height(self) -> int:
        """Height in [px]"""
        return self.value[2]


class ElementIDs(StrEnum):
    """Class to store all relevant HTML IDs in the dashboard interface"""

    # sACN Monitor section
    SACN_UNIVERSE_SELECT = "sacn-universe-select"
    SACN_SOURCE_NAME = "sacn-source-name"
    SACN_PRIORITY = "sacn-priority"
    SACN_TIMESTAMP = "sacn-timestamp"
    SACN_DMX_TABLE = "sacn-dmx-table"
    SACN_UPDATE_INTERVAL = "sacn-update-interval"

    # Fixture Patch section
    FIXTURE_SELECT = "fixture-select"
    FIXTURE_LABEL_VALUE = "fixture-label-value"
    FIXTURE_PIXELTYPE_VALUE = "fixture-pixeltype-value"
    FIXTURE_PIXELCOUNT_VALUE = "fixture-pixelcount-value"
    FIXTURE_SACNADDR_VALUE = "fixture-sacnaddr-value"
    FIXTURE_OUTPUT_VALUE = "fixture-output-value"

    # Console Logs section
    LOG_ENTRIES_SELECT = "log-entries-select"
    LOG_UPDATE_INTERVAL = "log-update-interval"
    CONSOLE_LOG_DISPLAY = "console-log-display"

    # Screen size detection
    SCREEN_SIZE_STORE = "screen-size-store"


class UiRefreshIntervals(IntEnum):
    """Refresh intervals for UI components (in milliseconds)"""

    SACN_MONITOR = 200
    CONSOLE_LOGS = 1000


@dataclass
class FixtureDisplayData:
    """Formatted fixture data for display in UI"""

    label: str
    pixel_type: str
    pixel_count: str
    sacn_address: str
    output_patch: str

    def asTuple(self) -> tuple:
        """Convert to tuple as required by dash callback"""
        return (
            self.label,
            self.pixel_type,
            self.pixel_count,
            self.sacn_address,
            self.output_patch,
        )


class PiLedBoxDashApp(dash.Dash):
    """Dash monitoring app for PiLedBox"""

    def __init__(
        self,
        fix_mgr: FixtureManager,
        sacn_mgr: sACNmanager,
        cfg_mgr: ConfigManager,
        **kwargs,
    ):
        """
        Initialize Dash app with access to all PiLedBox managers

        Args:
            fix_mgr: FixtureManager instance for LED strip configuration
            sacn_mgr: sACNmanager instance for DMX/sACN data
            cfg_mgr: ConfigManager instance for application config
            gpio_mgr: GpioManager instance for hardware control (None on non-RPi5)
            **kwargs: Additional arguments passed to dash.Dash
        """
        # Set default Dash configuration
        kwargs.setdefault("requests_pathname_prefix", "/dashboard/")
        kwargs.setdefault("title", APPNAME)
        kwargs.setdefault("update_title", None)  # Prevent "Updating..." in browser tab
        kwargs.setdefault("external_stylesheets", [dbc.themes.DARKLY])

        super().__init__(__name__, **kwargs)

        self.fix_mgr = fix_mgr
        self.sacn_mgr = sacn_mgr
        self.cfg_mgr = cfg_mgr

        self._setup_layout()
        self._register_callbacks()

    ###################
    ### MAIN LAYOUT ###
    ###################

    def _setup_layout(self):
        """Create the page layout"""
        self.layout = dbc.Container(
            [
                # Screen size detection
                dcc.Store(id=ElementIDs.SCREEN_SIZE_STORE, data="desktop"),
                self._create_header(),
                dbc.Row(
                    [
                        dbc.Col(
                            [self._create_sacn_monitor_card()],
                            width=12,
                            lg=9,
                            className="mb-3",
                        ),
                        dbc.Col(
                            [self._create_fixture_patch_card()],
                            width=12,
                            lg=3,
                            className="mb-3",
                        ),
                    ]
                ),
                dbc.Row([dbc.Col([self._create_console_log_card()], width=12)]),
            ],
            fluid=True,
            className="p-3",
        )

    ##############
    ### HEADER ###
    ##############

    def _create_header(self) -> dbc.Row:
        """Create header with title and host info"""

        hostname = f"{gethostname()}.local"
        ipv4 = self.cfg_mgr.config.input.ipv4
        iface = self.cfg_mgr.config.input.interface

        return dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    [
                                                        html.Strong(
                                                            APPNAME.upper(),
                                                            className="fs-5 text-primary bold",
                                                        ),
                                                    ],
                                                    width=12,
                                                    md=3,
                                                    className="mb-2 mb-md-0 d-flex align-items-center",
                                                ),
                                                dbc.Col(
                                                    [
                                                        html.Strong(
                                                            "HOSTNAME:",
                                                            className="me-1",
                                                        ),
                                                        html.Span(
                                                            hostname,
                                                            className="text-muted",
                                                        ),
                                                    ],
                                                    width=12,
                                                    md=3,
                                                    className="mb-2 mb-md-0 d-flex align-items-center",
                                                ),
                                                dbc.Col(
                                                    [
                                                        html.Strong(
                                                            "IP ADDRESS:",
                                                            className="me-1",
                                                        ),
                                                        html.Span(
                                                            ipv4, className="text-muted"
                                                        ),
                                                    ],
                                                    width=12,
                                                    md=3,
                                                    className="mb-2 mb-md-0 d-flex align-items-center",
                                                ),
                                                dbc.Col(
                                                    [
                                                        html.Strong(
                                                            "NET INTERFACE:",
                                                            className="me-1",
                                                        ),
                                                        html.Span(
                                                            iface,
                                                            className="text-muted",
                                                        ),
                                                    ],
                                                    width=12,
                                                    md=3,
                                                    class_name="d-flex align-items-center",
                                                ),
                                            ],
                                            className="text-center",
                                        )
                                    ],
                                    className="py-2",
                                )
                            ],
                            className="mb-3",
                        )
                    ],
                    width=12,
                )
            ]
        )

    ##################
    ### SACN PANEL ###
    ##################

    def _create_sacn_monitor_card(self) -> dbc.Card:
        """Create sACN Monitor card with live data updates"""
        # Get configured universes from fixture manager
        configured_universes = self.fix_mgr.get_universe_list()

        # Create dropdown options
        if configured_universes:
            universe_options = [
                {"label": str(uni), "value": str(uni)} for uni in configured_universes
            ]
            selected_universe = str(configured_universes[0])
        else:
            universe_options = [{"label": "No universes", "value": "0"}]
            selected_universe = "0"

        return dbc.Card(
            [
                dbc.CardHeader([html.H4("sACN MONITOR", className="mb-0 fs-5")]),
                dbc.CardBody(
                    [
                        dcc.Interval(
                            id=ElementIDs.SACN_UPDATE_INTERVAL,
                            interval=UiRefreshIntervals.SACN_MONITOR,
                            n_intervals=0,
                        ),
                        # Universe selector
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label(
                                            "Select sACN universe:", className="me-2"
                                        ),
                                        dbc.Select(
                                            id=ElementIDs.SACN_UNIVERSE_SELECT,
                                            options=universe_options,  # type: ignore[arg-type]
                                            value=selected_universe,
                                            className="mb-3",
                                        ),
                                    ]
                                )
                            ]
                        ),
                        # sACN universe Info
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    [
                                                        html.Strong(
                                                            "SOURCE NAME: ",
                                                            className="me-2",
                                                        ),
                                                        html.Span(
                                                            "Loading...",
                                                            className="text-muted",
                                                            id=ElementIDs.SACN_SOURCE_NAME,
                                                        ),
                                                    ],
                                                    width=12,
                                                    md=4,
                                                    className="mb-2 mb-md-0 d-flex align-items-center",
                                                ),
                                                dbc.Col(
                                                    [
                                                        html.Strong(
                                                            "sACN PRIORITY: ",
                                                            className="me-2",
                                                        ),
                                                        html.Span(
                                                            "---",
                                                            className="text-muted",
                                                            id=ElementIDs.SACN_PRIORITY,
                                                        ),
                                                    ],
                                                    width=12,
                                                    md=4,
                                                    className="mb-2 mb-md-0 d-flex align-items-center",
                                                ),
                                                dbc.Col(
                                                    [
                                                        html.Strong(
                                                            "TIMESTAMP: ",
                                                            className="me-2",
                                                        ),
                                                        html.Span(
                                                            "---",
                                                            className="text-muted",
                                                            id=ElementIDs.SACN_TIMESTAMP,
                                                        ),
                                                    ],
                                                    width=12,
                                                    md=4,
                                                    className="d-flex align-items-center",
                                                ),
                                            ],
                                            className="text-center",
                                        )
                                    ],
                                    className="py-2",
                                )
                            ],
                            className="mb-2",
                        ),
                        # DMX heatmap
                        html.Div(
                            id=ElementIDs.SACN_DMX_TABLE,
                            children=[self._create_dmx_table()],
                        ),
                    ]
                ),
            ]
        )

    def _create_dmx_table(
        self,
        dmx_values: Optional[list[int]] = None,
        config: DmxMapSpec = DmxMapSpec.DESKTOP,
    ) -> dcc.Graph:
        """
        Create full 512-channel DMX grid as Plotly heatmap

        Args:
            dmx_values: List of 512 DMX values (0-255). If None, creates dummy pattern data.
            config: DmxMapSpec enum specifying grid dimensions and height
        """
        # If no data provided, generate dummy pattern for initial display
        if dmx_values is None:
            dmx_values = []
            for i in range(512):
                if i < 128:
                    dmx_values.append(i * 2)  # Ramp up
                elif i < 256:
                    dmx_values.append(255 - (i - 128) * 2)  # Ramp down
                else:
                    dmx_values.append((i * 7) % 256)  # Pattern

        # Handle empty or incorrect length data
        if not dmx_values or len(dmx_values) != 512:
            dmx_values = [0] * 512

        # Get grid dimensions from config
        cols = config.cols
        rows = config.rows
        height = config.height
        grid = []
        channel_numbers = []

        for row in range(rows):
            grid_row = []
            channel_row = []
            for col in range(cols):
                ch = row * cols + col
                grid_row.append(dmx_values[ch])
                channel_row.append(ch + 1)  # Channel numbers are 1-indexed
            grid.append(grid_row)
            channel_numbers.append(channel_row)

        # Reverse the grid so channel 1 appears at top-left
        grid.reverse()
        channel_numbers.reverse()

        # Create heatmap
        fig = go.Figure(
            data=go.Heatmap(
                z=grid,
                text=grid,
                texttemplate="%{text}",
                textfont=dict(size=8, family="monospace", color="#ffffff"),
                customdata=channel_numbers,
                colorscale=[
                    [0, "rgba(33, 150, 243, 0.2)"],  # Dark blue at 0
                    [1, "rgba(33, 150, 243, 1.0)"],  # Bright blue at 255
                ],
                zmin=0,
                zmax=255,
                hovertemplate="<b>Channel %{customdata}</b><br>Value: %{z}<extra></extra>",
                showscale=False,  # Hide colorbar
                xgap=1,  # Horizontal gap between cells
                ygap=1,  # Vertical gap between cells
            )
        )

        fig.update_layout(
            autosize=True,
            height=height,
            margin=dict(l=5, r=5, t=5, b=5),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#aaa", size=9, family="monospace"),
            dragmode=False,  # Disable click-and-drag zoom
            xaxis=dict(
                showgrid=False, zeroline=False, showticklabels=False, visible=False
            ),
            yaxis=dict(
                showgrid=False, zeroline=False, showticklabels=False, visible=False
            ),
        )

        return dcc.Graph(
            figure=fig,
            config={
                "displayModeBar": False,  # Hide toolbar
                "responsive": True,  # Resize with window
                "scrollZoom": False,  # Disable scroll wheel zoom
                "doubleClick": False,  # Disable double-click zoom
                "staticPlot": False,  # Keep interactive for hover
            },
            style={"width": "100%", "height": f"{height}px"},
        )

    #####################
    ### FIXTURE PATCH ###
    #####################

    def _get_all_fixtures_flat(self) -> List[FixturePatch]:
        """Get all fixtures as a flat list"""
        fixtures_map: dict[GPIO, List[FixturePatch]] = self.fix_mgr.get_fixtures_all()
        all_fixtures: List[FixturePatch] = []
        for gpio, fixtures in fixtures_map.items():
            all_fixtures.extend(fixtures)
        return all_fixtures

    def _format_fixture_data(
        self, fixture: Optional[FixturePatch]
    ) -> FixtureDisplayData:
        """Format fixture data for display"""
        if not fixture:
            return FixtureDisplayData(
                label="---",
                pixel_type="---",
                pixel_count="---",
                sacn_address="---",
                output_patch="---",
            )

        return FixtureDisplayData(
            label=fixture.label,
            pixel_type=fixture.pixel_type.label,
            pixel_count=str(fixture.pixel_count),
            sacn_address=f"{fixture.universe}/{fixture.start_channel} >> {fixture.universe}/{fixture.end_channel}",
            output_patch=f"gpio{fixture.output.value} - queue pos [{fixture.pos_in_out_queue}]",
        )

    def _create_fixture_patch_card(self) -> dbc.Card:
        """Create Fixture Patch card"""
        all_fixtures = self._get_all_fixtures_flat()

        # Create dropdown options
        if all_fixtures:
            dropdown_options = [
                {"label": fixture.label, "value": fixture.label}
                for fixture in all_fixtures
            ]
            selected_value = all_fixtures[0].label
        else:
            dropdown_options = [{"label": "No fixtures", "value": "none"}]
            selected_value = "none"

        # Format first fixture data
        first_fixture = all_fixtures[0] if all_fixtures else None
        data = self._format_fixture_data(first_fixture)

        fixture_label = data.label
        pixel_type = data.pixel_type
        pixel_count = data.pixel_count
        sacn_address = data.sacn_address
        output_patch = data.output_patch

        return dbc.Card(
            [
                dbc.CardHeader([html.H4("FIXTURE PATCH", className="mb-0 fs-5")]),
                dbc.CardBody(
                    [
                        # Fixture selector
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label(
                                            "Select fixture patch:", className="me-2"
                                        ),
                                        dbc.Select(
                                            id=ElementIDs.FIXTURE_SELECT,
                                            options=dropdown_options,  # type: ignore[arg-type]
                                            value=selected_value,
                                            className="mb-4",
                                        ),
                                    ]
                                )
                            ]
                        ),
                        # Fixture Info Table
                        dbc.Table(
                            [
                                html.Tbody(
                                    [
                                        html.Tr(
                                            [
                                                html.Td(
                                                    "FIXTURE LABEL:",
                                                    className="fw-bold",
                                                    style={"width": "40%"},
                                                ),
                                                html.Td(
                                                    fixture_label,
                                                    className="text-muted",
                                                    id=ElementIDs.FIXTURE_LABEL_VALUE,
                                                ),
                                            ]
                                        ),
                                        html.Tr(
                                            [
                                                html.Td(
                                                    "PIXEL TYPE:", className="fw-bold"
                                                ),
                                                html.Td(
                                                    pixel_type,
                                                    className="text-muted",
                                                    id=ElementIDs.FIXTURE_PIXELTYPE_VALUE,
                                                ),
                                            ]
                                        ),
                                        html.Tr(
                                            [
                                                html.Td(
                                                    "PIXEL COUNT:", className="fw-bold"
                                                ),
                                                html.Td(
                                                    pixel_count,
                                                    className="text-muted",
                                                    id=ElementIDs.FIXTURE_PIXELCOUNT_VALUE,
                                                ),
                                            ]
                                        ),
                                        html.Tr(
                                            [
                                                html.Td(
                                                    "sACN ADDRESS:", className="fw-bold"
                                                ),
                                                html.Td(
                                                    sacn_address,
                                                    className="text-muted",
                                                    id=ElementIDs.FIXTURE_SACNADDR_VALUE,
                                                ),
                                            ]
                                        ),
                                        html.Tr(
                                            [
                                                html.Td(
                                                    "OUTPUT PATCH:", className="fw-bold"
                                                ),
                                                html.Td(
                                                    output_patch,
                                                    className="text-muted",
                                                    id=ElementIDs.FIXTURE_OUTPUT_VALUE,
                                                ),
                                            ]
                                        ),
                                    ]
                                )
                            ],
                            bordered=True,
                            hover=True,
                            size="sm",
                        ),
                    ]
                ),
            ]
        )

    ####################
    ### CONSOLE LOGS ###
    ####################

    def _create_console_log_card(self) -> dbc.Card:
        """Create Console Log card with live log updates"""
        return dbc.Card(
            [
                dbc.CardHeader(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label(
                                            "Log entries:", className="me-2 mb-0"
                                        ),
                                        dbc.Select(
                                            id=ElementIDs.LOG_ENTRIES_SELECT,
                                            options=[
                                                {"label": "20", "value": "20"},
                                                {"label": "40", "value": "40"},
                                                {"label": "60", "value": "60"},
                                                {"label": "80", "value": "80"},
                                                {"label": "100", "value": "100"},
                                            ],
                                            value="20",
                                            style={
                                                "width": "100px",
                                                "display": "inline-block",
                                            },
                                        ),
                                    ],
                                    width="auto",
                                ),
                                dbc.Col(
                                    [html.H4("CONSOLE LOG", className="mb-0 fs-5")],
                                    className="text-center",
                                ),
                                dbc.Col(width="auto"),  # Spacer for symmetry
                            ],
                            align="center",
                        )
                    ]
                ),
                dbc.CardBody(
                    [
                        dcc.Interval(
                            id=ElementIDs.LOG_UPDATE_INTERVAL,
                            interval=UiRefreshIntervals.CONSOLE_LOGS,
                            n_intervals=0,
                        ),
                        # Log display container
                        html.Div(
                            id=ElementIDs.CONSOLE_LOG_DISPLAY,
                            children=[html.Div("Loading logs...")],
                            style={
                                "font-family": "monospace",
                                "font-size": "0.6rem",
                                "background-color": "#1a1a1a",
                                "padding": "15px",
                                "border-radius": "5px",
                                "max-height": "220px",
                                "overflow-y": "auto",
                                "white-space": "pre-wrap",
                            },
                        ),
                    ]
                ),
            ]
        )

    #################
    ### CALLBACKS ###
    #################

    def _register_callbacks(self):
        """Register Dash callbacks"""

        @self.callback(
            [
                Output(ElementIDs.SACN_SOURCE_NAME, "children"),
                Output(ElementIDs.SACN_PRIORITY, "children"),
                Output(ElementIDs.SACN_TIMESTAMP, "children"),
                Output(ElementIDs.SACN_DMX_TABLE, "children"),
            ],
            [
                Input(ElementIDs.SACN_UPDATE_INTERVAL, "n_intervals"),
                Input(ElementIDs.SACN_UNIVERSE_SELECT, "value"),
                Input(ElementIDs.SCREEN_SIZE_STORE, "data"),
            ],
        )
        def update_sacn_monitor(n_intervals, selected_universe_str, screen_size):
            """Update sACN monitor display"""

            config = (
                DmxMapSpec.MOBILE if screen_size == "mobile" else DmxMapSpec.DESKTOP
            )

            try:
                selected_universe = int(selected_universe_str)
            except (ValueError, TypeError):
                # If conversion fails, return placeholder values
                return (
                    "No universe selected",
                    "---",
                    "---",
                    [self._create_dmx_table([0] * 512, config)],
                )

            # Get sACN data report from manager
            try:
                universe_report = self.sacn_mgr.getUniverseInfoReport()
            except Exception:
                # If error getting data, return placeholders
                return (
                    "Error reading data",
                    "---",
                    "---",
                    [self._create_dmx_table([0] * 512, config)],
                )

            # Check if selected universe has data
            if selected_universe in universe_report.root:
                universe_info = universe_report.root[selected_universe]

                # Extract data
                source_name = universe_info.sourceName
                priority = str(universe_info.priority)
                timestamp = universe_info.latestTimeStamp[11:]  # Extract time only
                dmx_data = list(universe_info.dmxData)

                dmx_table = self._create_dmx_table(dmx_data, config)

                return source_name, priority, timestamp, [dmx_table]
            else:
                # No data received
                return "---", "---", "---", [self._create_dmx_table([0] * 512, config)]

        @self.callback(
            [
                Output(ElementIDs.FIXTURE_LABEL_VALUE, "children"),
                Output(ElementIDs.FIXTURE_PIXELTYPE_VALUE, "children"),
                Output(ElementIDs.FIXTURE_PIXELCOUNT_VALUE, "children"),
                Output(ElementIDs.FIXTURE_SACNADDR_VALUE, "children"),
                Output(ElementIDs.FIXTURE_OUTPUT_VALUE, "children"),
            ],
            Input(ElementIDs.FIXTURE_SELECT, "value"),
        )
        def update_fixture_info(selected_label):
            """Update fixture info table when dropdown selection changes"""
            all_fixtures = self._get_all_fixtures_flat()

            # Find selected fixture
            selected_fixture = next(
                (f for f in all_fixtures if f.label == selected_label), None
            )

            # Format and return fixture data
            data = self._format_fixture_data(selected_fixture)
            return data.asTuple()

        @self.callback(
            Output(ElementIDs.CONSOLE_LOG_DISPLAY, "children"),
            [
                Input(ElementIDs.LOG_UPDATE_INTERVAL, "n_intervals"),
                Input(ElementIDs.LOG_ENTRIES_SELECT, "value"),
            ],
        )
        def update_console_logs(n_intervals, log_count_str):
            """Update console log display every second"""
            log_count = int(log_count_str)

            log_entries = getLastLogEntries(log_count)
            log_entries.reverse()  # display most recent up top

            if log_entries:
                return [html.Div(log) for log in log_entries]
            else:
                return [html.Div("No logs available")]

        # Clientside callback to detect screen size
        self.clientside_callback(
            """
            function(n_intervals) {
                // Bootstrap lg breakpoint is 992px
                return window.innerWidth >= 992 ? 'desktop' : 'mobile';
            }
            """,
            Output(ElementIDs.SCREEN_SIZE_STORE, "data"),
            Input(ElementIDs.SACN_UPDATE_INTERVAL, "n_intervals"),
        )
