"""
Integration and regression tests for ContractDiffEngine:
Tests OpenAPI/Swagger, GraphQL, and Protocol Buffers contract diffing
and breaking change detection.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.contract_diff import ContractDiffEngine


class TestContractDiffEngine(unittest.TestCase):

    def test_openapi_diff(self):
        o1 = """
openapi: 3.0.0
info:
  title: User API
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      parameters:
        - name: limit
          in: query
          required: false
          schema:
            type: integer
    delete:
      summary: Delete user
"""
        o2 = """
openapi: 3.0.0
info:
  title: User API
  version: 2.0.0
paths:
  /users:
    get:
      summary: List users
      parameters:
        - name: limit
          in: query
          required: true
          schema:
            type: integer
        - name: page
          in: query
          required: false
          schema:
            type: integer
  /orders:
    get:
      summary: Orders
"""
        report = ContractDiffEngine.diff_contracts(o1, o2, "api1.yaml", "api2.yaml")
        self.assertEqual(report.contract_type, "OpenAPI")
        self.assertTrue(report.has_breaking_changes)
        # /users DELETE removed + limit changed to required
        self.assertGreaterEqual(report.breaking_count, 2)
        # /orders added + page parameter added
        self.assertGreaterEqual(report.additive_count, 2)

    def test_graphql_diff(self):
        g1 = """
type User {
  id: ID!
  name: String
  email: String!
}

enum Role {
  USER
  ADMIN
  GUEST
}
"""
        g2 = """
type User {
  id: ID!
  name: String
  email: String
  age: Int
}

enum Role {
  USER
  ADMIN
}
"""
        report = ContractDiffEngine.diff_contracts(g1, g2, "schema1.graphql", "schema2.graphql")
        self.assertEqual(report.contract_type, "GraphQL")
        self.assertTrue(report.has_breaking_changes)
        # email became nullable + GUEST enum removed
        self.assertGreaterEqual(report.breaking_count, 2)
        # age added
        self.assertGreaterEqual(report.additive_count, 1)

    def test_protobuf_diff(self):
        p1 = """
syntax = "proto3";
package api;

message User {
  string id = 1;
  string email = 2;
}

service UserService {
  rpc GetUser (UserRequest) returns (User);
}
"""
        p2 = """
syntax = "proto3";
package api;

message User {
  string id = 1;
  int32 email = 2;
  string phone = 3;
}

service UserService {
  rpc GetUser (UserRequest) returns (User);
  rpc ListUsers (ListRequest) returns (ListResponse);
}
"""
        report = ContractDiffEngine.diff_contracts(p1, p2, "service1.proto", "service2.proto")
        self.assertEqual(report.contract_type, "Protobuf")
        self.assertTrue(report.has_breaking_changes)
        # email type changed string -> int32
        self.assertGreaterEqual(report.breaking_count, 1)
        # phone field added + ListUsers rpc added
        self.assertGreaterEqual(report.additive_count, 2)


if __name__ == "__main__":
    unittest.main()
