from __future__ import annotations
from pprint import pprint
from typing import List, Dict, Union
from datetime import datetime
from enum import Enum
from functools import cached_property
from attr import dataclass
from pandas import value_counts
import vcd
from vcd.reader import TokenKind
from dataclasses import dataclass

class VcdSimulation:
    _tokens: List[vcd.reader.Token]

    def __init__(self, vcd_stream: vcd.reader.HasReadinto):
        self._tokens = list(vcd.reader.tokenize(vcd_stream))

    def _filtered_tokens(self, tokenKind: TokenKind):
        return [token for token in self._tokens if tokenKind == token.kind]

    def date(self) -> datetime:
        token = self._filtered_tokens(TokenKind.DATE)[0]
        return datetime.strptime(token.data.strip(), '%a %b %d %H:%M:%S %Y')

    @cached_property
    def timescale(self) -> vcd.reader.Timescale:
        token = self._filtered_tokens(TokenKind.TIMESCALE)[0]
        return token.data

    @cached_property
    def scope_vars(self) -> Dict[vcd.reader.ScopeDecl, Dict[int, vcd.reader.VarDecl]]:
        acc = {}
        for token in self._tokens:
            if token.kind == TokenKind.SCOPE:
                scope = token.data.ident
                acc[scope] = {}
            elif token.kind == TokenKind.VAR:
                var = token.data.reference
                if var not in acc[scope]:
                    acc[scope][var] = {}
                acc[scope][var][token.data.bit_index] = token.data
                
        return acc

    @cached_property
    def time_changes(self) -> Dict[int, Union[vcd.reader.ScalarChange, vcd.reader.VectorChange, vcd.reader.RealChange, vcd.reader.StringChange]]:
        acc = {}
        for token in self._tokens:
            if token.kind == TokenKind.CHANGE_TIME:
                time = token.data
                acc[time] = []
            elif token.kind == TokenKind.CHANGE_SCALAR or token.kind == TokenKind.CHANGE_VECTOR or token.kind == TokenKind.CHANGE_REAL == token.kind == TokenKind.CHANGE_STRING:
                change = token.data
                acc[time].append(change)
        return acc

    def to_events(self, vars: Dict[Union[None, int], vcd.reader.VarDecl])-> List[ChannelEvent]:
        acc = []
        value = ['X'] * len(vars)
        vars = sorted(vars.values(), key=lambda x: x.bit_index, reverse=True)
        for time, changes in self.time_changes.items():
            has_changed = False
            for change in changes:
                for var in vars:
                    if change.id_code == var.id_code:
                        index = var.bit_index if var.bit_index is not None else 0
                        value[index] = change.value
                        has_changed = True
            if has_changed:
                event = ChannelEvent(time, ''.join(value))
                acc.append(event)
        return acc 

    def to_channel(self) -> List[Channel]:
        acc = []
        for module, channels in self.scope_vars.items():
            for channel_name, vars in channels.items():
                size = len(vars)
                events = self.to_events(vars)
                acc.append(Channel(size, module, channel_name, events))
        return acc

    def to_simulation(self) -> Simulation:
        return Simulation(self.to_channel())
                
        

class Signal(Enum):
    ONE = 'H'
    ZERO = 'L'
    UNKNOWN = 'X'
    IMPEDANCE = 'Z'
    

@dataclass
class Simulation:
    channels: List[Channel]

    def to_tikz(self, start, end, channel_names=None):
        tikz_table = ['\\begin{{tikztimingtable}}']
        channels = self.channels
        if channel_names is not None: 
            channels = [c for c in self.channels if c.name in channel_names] 
        for channel in channels:
            tikz_table.append('\t'+channel.to_tikz_line(start, end))
        tikz_table.append('\\end{{tikztimingtable}}')

        return '\n'.join(tikz_table)

@dataclass
class Channel:
    size: int
    module: str
    name: str
    events: List[ChannelEvent]

    def value_at(self, time) -> str:
        i = 0
        while i < len(self.events) and self.events[i].time <= time:
            i += 1
        if i == 0:
            return 'X' # TODO completar com resultado da Enum
        return self.events[i-1].value

    def next_event(self, time) -> ChannelEvent:
        i = 0
        while i < len(self.events) and self.events[i].time <= time:
            i += 1
        if i >= len(self.events):
            return None
        return self.events[i]

    def to_tikz_line(self, start, end):
        tikz_line = [self.name+' &']
        current_value = self.value_at(start)
        current_time = start
        while current_time < end:
            next_event = self.next_event(current_time)
            if next_event is None:
                next_event_time = end
            else:
                next_event_time = next_event.time
            signal_duration = next_event_time - current_time
            signal_type = current_value
            tikz_line.append(f'{signal_duration}{{{signal_type}}}') # TODO completar com resultado da Enum
            if next_event is None:
                break
            current_value = next_event.value
            current_time = next_event.time

        return ' '.join(tikz_line) 

@dataclass
class ChannelEvent:
    time: int
    value: str

if __name__ == '__main__':
    clk = Channel(1, 'teste', 'clock', [
        ChannelEvent( 0, 0),
        ChannelEvent(10, 1),
        ChannelEvent(20, 0),
        ChannelEvent(30, 1),
        ChannelEvent(40, 0),
        ChannelEvent(50, 1),
    ])
    enable = Channel(1, 'teste', 'enable', [
        ChannelEvent( 0, 0),
        ChannelEvent(30, 1),
        # ChannelEvent(50, 0),
    ])
    simulation = Simulation([
        clk,
        enable
    ])
    # print(clk.to_tikz_line(0,50))
    # print(clk.to_tikz_line(5,20))
    # print(clk.to_tikz_line(0,15))
    # print(clk.to_tikz_line(5,15))
    # print(simulation.to_tikz(0, 50))

    with open('fluxo_dados.vcd', 'rb') as f:
        vcd_sim = VcdSimulation(f)
    # sim = vcd_sim.to_simulation()
    pprint(vcd_sim.to_simulation())
    # print(simulation.to_tikz(0, 50))
